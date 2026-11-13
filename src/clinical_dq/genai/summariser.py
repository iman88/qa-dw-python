"""Safety narratives: the GenAI feature under test.

Given a subject's adverse events from the warehouse, write a short structured safety
narrative. Three implementations share one interface:

* ``TemplateSummariser``: deterministic, offline. The default, so the suite runs in CI
  with no API key and no cost.
* ``ClaudeSummariser``: calls Claude with structured output (a Pydantic model), so the
  response is schema-valid by construction and the evaluator can check the facts.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from pydantic import BaseModel, Field

log = logging.getLogger("clinical_dq.genai")


class SafetyNarrative(BaseModel):
    subject_id: str = Field(description="Subject identifier exactly as given")
    total_events: int = Field(description="Number of adverse event records given")
    serious_events: int = Field(description="Number of records with serious = true")
    max_grade: int = Field(description="Highest toxicity grade among the records, 0 if there are none")
    event_terms: list[str] = Field(description="Distinct event terms, exactly as written in the records")
    narrative: str = Field(description="Plain clinical English, at most 120 words")


class Summariser(Protocol):
    name: str

    def summarise(self, subject_id: str, events: list[dict[str, Any]]) -> SafetyNarrative: ...


class NarrativeRefused(RuntimeError):
    """The model declined the request (stop_reason == "refusal")."""


def _facts(subject_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    terms = sorted({e["meddra_pt"] for e in events})
    return {
        "subject_id": subject_id,
        "total_events": len(events),
        "serious_events": sum(1 for e in events if e["is_serious"]),
        "max_grade": max((int(e["grade"]) for e in events), default=0),
        "event_terms": terms,
    }


class TemplateSummariser:
    name = "template"

    def summarise(self, subject_id: str, events: list[dict[str, Any]]) -> SafetyNarrative:
        f = _facts(subject_id, events)
        if not events:
            text = f"Subject {subject_id} has no adverse events recorded."
        else:
            serious = (
                f"{f['serious_events']} of them serious" if f["serious_events"] else "none of them serious"
            )
            text = (
                f"Subject {subject_id} reported {f['total_events']} adverse events, {serious}. "
                f"The highest toxicity grade was {f['max_grade']}. "
                f"Reported terms: {', '.join(f['event_terms'])}."
            )
        return SafetyNarrative(**f, narrative=text)


SYSTEM_PROMPT = """You write short safety narratives for clinical trial subjects, for a medical monitor.

Work only from the adverse event records in the user message. Every count, grade and event
term in your answer must come from those records. Do not add events, dates, numbers,
diagnoses or patient details that are not in the records, and do not speculate about causes.

Fill the structured fields exactly: count the records, count those with is_serious true, take
the highest grade, and list each distinct event term as written. In the narrative, say how many
events there were, say plainly which ones were serious, and give the highest grade. Keep it
under 120 words, in plain clinical English. If there are no records, say so in one sentence."""


class ClaudeSummariser:
    name = "claude"

    def __init__(self, model: str = "claude-opus-5-5", client: Any | None = None) -> None:
        import anthropic  # imported here so the offline suite never needs credentials

        self.model = model
        self.client = client or anthropic.Anthropic()
        self.last_usage: dict[str, int] = {}

    def summarise(self, subject_id: str, events: list[dict[str, Any]]) -> SafetyNarrative:
        records = [
            {k: e[k] for k in ("ae_id", "meddra_pt", "grade", "is_serious", "onset_date", "outcome")}
            for e in events
        ]
        payload = json.dumps({"subject_id": subject_id, "adverse_events": records}, default=str, indent=2)
        response = self.client.beta.messages.parse(
            model=self.model,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Adverse event records:\n{payload}"}],
            output_format=SafetyNarrative,
            output_config={"effort": "low"},  # short, fully specified task
            # If a safety classifier declines, retry server-side on the recommended model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            category = response.stop_details.category if response.stop_details else None
            raise NarrativeRefused(f"Claude declined the narrative request (category={category})")
        if response.parsed_output is None:
            raise RuntimeError(f"No structured output (stop_reason={response.stop_reason})")
        self.last_usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        return response.parsed_output


class FallbackSummariser:
    """Claude first; the deterministic template whenever Claude cannot answer.

    The service must keep working when the model does not: no network, no credentials, rate
    limits, overload (529), server errors, a refusal or an unparseable answer. In all of those
    cases the template narrative is returned and ``last_source`` says so, so the API can
    report it (header ``X-Narrative-Source``) and nobody mistakes a fallback for a model answer.
    """

    name = "claude-with-fallback"

    def __init__(
        self, primary: Summariser | None, fallback: Summariser | None = None, startup_error: str | None = None
    ) -> None:
        self.primary = primary
        self.fallback = fallback or TemplateSummariser()
        self.last_source = "template-fallback" if primary is None else "claude"
        self.last_error: str | None = startup_error
        self.fallbacks_used = 0

    def summarise(self, subject_id: str, events: list[dict[str, Any]]) -> SafetyNarrative:
        if self.primary is not None:
            try:
                result = self.primary.summarise(subject_id, events)
                self.last_source, self.last_error = "claude", None
                return result
            except Exception as exc:  # any model-side failure: degrade, never fail the request
                self.last_error = f"{type(exc).__name__}: {exc}"
                log.warning("Claude unavailable, using template narrative (%s)", self.last_error)
        self.fallbacks_used += 1
        self.last_source = "template-fallback"
        return self.fallback.summarise(subject_id, events)


def get_summariser(provider: str, model: str = "claude-opus-5-5", fallback: bool = True) -> Summariser:
    """``template``: offline, deterministic. ``claude``: Claude with automatic template failover.

    ``fallback=False`` gives the bare Claude summariser; use it only for live evaluation, where a
    silent fallback would score the template instead of the model.
    """
    if provider == "template":
        return TemplateSummariser()
    if provider != "claude":
        raise ValueError(f"Unknown GENAI_PROVIDER {provider!r}; use 'template' or 'claude'")
    if not fallback:
        return ClaudeSummariser(model=model)
    try:
        return FallbackSummariser(ClaudeSummariser(model=model))
    except Exception as exc:  # SDK missing or client cannot be built: start in fallback mode
        log.warning("Claude client could not be created, narratives use the template (%s)", exc)
        return FallbackSummariser(None, startup_error=f"{type(exc).__name__}: {exc}")

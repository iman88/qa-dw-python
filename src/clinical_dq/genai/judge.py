"""Judging narrative quality beyond the deterministic metrics.

The deterministic metrics catch wrong counts and invented events. Whether a narrative is clear,
clinically appropriate and fit for a medical monitor needs judgement: a judge model, or a person.
A judge model is only trusted after calibration: on narratives that people have already labelled,
its verdicts must agree with theirs (Cohen's kappa of at least 0.6, see stats.cohen_kappa).

* ClaudeJudge:     Claude with a rubric and structured output (live, costs money)
* ReferenceJudge:  a rule-based judge with the same interface, offline and deterministic; it lets
                   the calibration itself be tested without calling a model
"""

from __future__ import annotations

import re
from typing import Any, Protocol

from pydantic import BaseModel, Field


class Verdict(BaseModel):
    acceptable: bool = Field(description="True if a medical monitor could rely on this narrative as written")
    faithfulness: int = Field(description="1-5: every statement is supported by the records")
    clarity: int = Field(description="1-5: short, plain, unambiguous clinical English")
    reason: str = Field(description="One sentence explaining the verdict")


class Judge(Protocol):
    name: str

    def judge(self, events: list[dict[str, Any]], narrative: str) -> Verdict: ...


RUBRIC = """You review safety narratives written for a clinical trial medical monitor.

You get the subject's adverse event records and a narrative. Judge only the narrative against the
records. It is acceptable only if all of these hold:
- every event, count, grade and seriousness it states matches the records; nothing is invented;
- every serious event in the records is mentioned as serious;
- it is plain, unambiguous clinical English, without speculation about causes.
Score faithfulness and clarity from 1 (poor) to 5 (excellent) and give a one-sentence reason."""


class ClaudeJudge:
    """Claude Sonnet as the judge: capable enough for a rubric, cheaper than the model it judges."""

    name = "claude-judge"

    def __init__(self, model: str = "claude-sonnet-5-5", client: Any | None = None) -> None:
        import anthropic

        self.model = model
        self.client = client or anthropic.Anthropic()

    def judge(self, events: list[dict[str, Any]], narrative: str) -> Verdict:
        response = self.client.beta.messages.parse(
            model=self.model,
            max_tokens=2000,
            system=RUBRIC,
            messages=[{"role": "user", "content": f"Records: {events}\n\nNarrative: {narrative}"}],
            output_format=Verdict,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise RuntimeError(f"judge gave no verdict (stop_reason={response.stop_reason})")
        return response.parsed_output


class ReferenceJudge:
    """Rule-based judge: rejects narratives that name terms not in the records or hide a serious event."""

    name = "reference-judge"

    def judge(self, events: list[dict[str, Any]], narrative: str) -> Verdict:
        text = narrative.lower()
        serious = any(e["is_serious"] for e in events)
        hides_serious = serious and "serious" not in text
        known = {e["meddra_pt"].lower() for e in events}
        invented = [
            w
            for w in re.findall(r"[a-z][a-z ]+(?:infarction|failure|sepsis|stroke)", text)
            if w.strip() not in known
        ]
        acceptable = not hides_serious and not invented
        return Verdict(
            acceptable=acceptable,
            faithfulness=5 if acceptable else 2,
            clarity=4,
            reason="consistent with the records"
            if acceptable
            else ("hides a serious event" if hides_serious else f"invents {invented[0].strip()}"),
        )

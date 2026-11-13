"""Deterministic evaluation of safety narratives against the source records.

No second LLM is needed for the checks that matter most in a regulated setting: did the
model count correctly, did it invent anything, did it hide a serious event. Those are
checked against the data, exactly. Each metric is pass/fail with a reason.

Metrics
-------
subject_match        the narrative is about the subject that was asked for
count_accuracy       total and serious counts equal the records
max_grade_accuracy   highest grade equals the records
term_grounding       every term in event_terms exists in the records (no invented events)
term_coverage        every term in the records appears in event_terms (nothing left out)
numeric_grounding    every number in the narrative text is a count, grade or id from the data
serious_disclosed    if any event is serious, the narrative says "serious"
length_limit         narrative is at most 120 words
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from clinical_dq.genai.summariser import SafetyNarrative

MAX_WORDS = 120
_NUMBER = re.compile(r"(?<![\w-])\d+(?![\w-])")


@dataclass
class EvalResult:
    case_id: str
    summariser: str
    metrics: dict[str, bool] = field(default_factory=dict)
    reasons: dict[str, str] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(self.metrics.values())

    @property
    def failed_metrics(self) -> list[str]:
        return [m for m, ok in self.metrics.items() if not ok]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "summariser": self.summariser,
            "passed": self.passed,
            "metrics": self.metrics,
            "reasons": self.reasons,
        }


def evaluate(
    case_id: str, summariser: str, subject_id: str, events: list[dict[str, Any]], out: SafetyNarrative
) -> EvalResult:
    result = EvalResult(case_id, summariser)

    def metric(name: str, ok: bool, reason: str) -> None:
        result.metrics[name] = ok
        if not ok:
            result.reasons[name] = reason

    terms = {e["meddra_pt"] for e in events}
    serious = sum(1 for e in events if e["is_serious"])
    max_grade = max((int(e["grade"]) for e in events), default=0)

    metric("subject_match", out.subject_id == subject_id, f"expected {subject_id}, got {out.subject_id}")
    metric(
        "count_accuracy",
        out.total_events == len(events) and out.serious_events == serious,
        f"expected total={len(events)} serious={serious}, got total={out.total_events} "
        f"serious={out.serious_events}",
    )
    metric("max_grade_accuracy", out.max_grade == max_grade, f"expected {max_grade}, got {out.max_grade}")

    invented = sorted(set(out.event_terms) - terms)
    metric("term_grounding", not invented, f"terms not in the records: {invented}")
    missing = sorted(terms - set(out.event_terms))
    metric("term_coverage", not missing, f"terms left out: {missing}")

    allowed = {str(n) for n in (len(events), serious, max_grade, *range(0, 6))}
    allowed |= set(re.findall(r"\d+", subject_id))
    stray = sorted({n for n in _NUMBER.findall(out.narrative) if n not in allowed}, key=int)
    metric("numeric_grounding", not stray, f"numbers not supported by the data: {stray}")

    metric(
        "serious_disclosed",
        serious == 0 or "serious" in out.narrative.lower(),
        "serious events exist but the narrative never says so",
    )
    words = len(out.narrative.split())
    metric("length_limit", words <= MAX_WORDS, f"{words} words, limit {MAX_WORDS}")
    return result

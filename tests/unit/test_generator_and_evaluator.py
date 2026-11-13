"""Generator determinism and evaluator behaviour, no database."""

from collections import Counter

import pytest

from clinical_dq.data.generator import generate
from clinical_dq.genai.evaluator import evaluate
from clinical_dq.genai.summariser import SafetyNarrative, TemplateSummariser
from tests.support import HallucinatingSummariser

pytestmark = pytest.mark.unit

EVENTS = [
    {"ae_id": "AE-1", "meddra_pt": "Nausea", "grade": 2, "is_serious": False},
    {"ae_id": "AE-2", "meddra_pt": "Neutropenia", "grade": 4, "is_serious": True},
]


def test_same_seed_same_data() -> None:
    a, b = generate(seed=7, subjects_per_study=10), generate(seed=7, subjects_per_study=10)
    assert a.stats == b.stats
    assert a.source["adverse_event"] == b.source["adverse_event"]


def test_feed_has_redeliveries_and_replays_to_source_state() -> None:
    data = generate(seed=7, subjects_per_study=10)
    seqs = Counter(e["change_seq"] for e in data.feed["visit"])
    assert any(n > 1 for n in seqs.values()), "expected at-least-once duplicates in the feed"
    latest: dict = {}
    for e in sorted(data.feed["visit"], key=lambda e: e["change_seq"]):
        latest[e["visit_id"]] = e
    replayed = {k: v["status"] for k, v in latest.items() if v["op"] != "D"}
    assert replayed == {v["visit_id"]: v["status"] for v in data.source["visit"]}


def test_template_summary_passes_every_metric() -> None:
    out = TemplateSummariser().summarise("SUBJ-0001", EVENTS)
    assert evaluate("t", "template", "SUBJ-0001", EVENTS, out).passed


def test_hallucination_is_caught() -> None:
    out = HallucinatingSummariser().summarise("SUBJ-0001", EVENTS)
    result = evaluate("h", "hallucinating", "SUBJ-0001", EVENTS, out)
    assert {"count_accuracy", "term_grounding", "numeric_grounding"} <= set(result.failed_metrics)


def test_hidden_serious_event_is_caught() -> None:
    out = SafetyNarrative(
        subject_id="SUBJ-0001",
        total_events=2,
        serious_events=1,
        max_grade=4,
        event_terms=["Nausea", "Neutropenia"],
        narrative="Subject SUBJ-0001 had 2 adverse events, highest grade 4.",
    )
    result = evaluate("s", "manual", "SUBJ-0001", EVENTS, out)
    assert result.failed_metrics == ["serious_disclosed"]


def test_invented_number_in_text_is_caught() -> None:
    out = TemplateSummariser().summarise("SUBJ-0001", EVENTS)
    out = out.model_copy(update={"narrative": out.narrative + " Onset was on day 17."})
    assert evaluate("n", "manual", "SUBJ-0001", EVENTS, out).failed_metrics == ["numeric_grounding"]

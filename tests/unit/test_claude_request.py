"""ClaudeSummariser against a fake HTTP transport: checks the request we send, no network, no cost."""

import json

import anthropic
import httpx2 as httpx  # the SDK uses httpx2, so the mock transport must too
import pytest

from clinical_dq.genai.evaluator import evaluate
from clinical_dq.genai.summariser import ClaudeSummariser, NarrativeRefused

pytestmark = pytest.mark.unit

EVENTS = [
    {
        "ae_id": "AE-1",
        "meddra_pt": "Nausea",
        "grade": 2,
        "is_serious": False,
        "onset_date": "2025-01-02",
        "outcome": "RECOVERED",
    },
    {
        "ae_id": "AE-2",
        "meddra_pt": "Neutropenia",
        "grade": 4,
        "is_serious": True,
        "onset_date": "2025-01-09",
        "outcome": "RECOVERING",
    },
]
NARRATIVE = {
    "subject_id": "SUBJ-0001",
    "total_events": 2,
    "serious_events": 1,
    "max_grade": 4,
    "event_terms": ["Nausea", "Neutropenia"],
    "narrative": "Subject SUBJ-0001 had 2 adverse events. Neutropenia (grade 4) was serious.",
}


def _client(captured: list[httpx.Request], stop_reason: str = "end_turn") -> anthropic.Anthropic:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        content = [] if stop_reason == "refusal" else [{"type": "text", "text": json.dumps(NARRATIVE)}]
        body = {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "stop_details": {"type": "refusal", "category": None, "explanation": None}
            if stop_reason == "refusal"
            else None,
            "usage": {"input_tokens": 50, "output_tokens": 40},
        }
        return httpx.Response(200, json=body)

    return anthropic.Anthropic(
        api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)), max_retries=0
    )


def test_request_shape_and_parsed_output() -> None:
    captured: list[httpx.Request] = []
    out = ClaudeSummariser(client=_client(captured)).summarise("SUBJ-0001", EVENTS)

    request = captured[0]
    sent = json.loads(request.content)
    assert request.url.path == "/v1/messages"
    assert "server-side-fallback-2026-07-01" in request.headers["anthropic-beta"]
    assert sent["model"] == "claude-opus-5-5"
    assert sent["fallbacks"] == "default"
    assert sent["output_config"]["effort"] == "low"
    assert sent["output_config"]["format"]["type"] == "json_schema"
    assert "Neutropenia" in sent["messages"][0]["content"]
    assert "thinking" not in sent and "temperature" not in sent
    assert evaluate("mock", "claude", "SUBJ-0001", EVENTS, out).passed


def test_refusal_is_raised_not_parsed() -> None:
    with pytest.raises(NarrativeRefused):
        ClaudeSummariser(client=_client([], stop_reason="refusal")).summarise("SUBJ-0001", EVENTS)

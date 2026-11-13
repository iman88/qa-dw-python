"""Helpers shared by step modules."""

from __future__ import annotations

import json
import socket
from typing import Any

import anthropic
import httpx2

from clinical_dq.genai.summariser import ClaudeSummariser, SafetyNarrative, TemplateSummariser

try:  # Allure is optional: attachments only appear when run with --alluredir
    import allure
except ImportError:  # pragma: no cover
    allure = None


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def attach(name: str, payload: Any) -> None:
    if allure is not None:
        allure.attach(
            json.dumps(payload, indent=2, default=str), name=name, attachment_type=allure.attachment_type.JSON
        )


# ----------------------------------------------------------------------------- Claude outages
FAILURES = {
    "server error": 500,
    "overloaded": 529,
    "rate limited": 429,
    "invalid credentials": 401,
}


def unavailable_claude(failure: str) -> ClaudeSummariser:
    """A real ClaudeSummariser whose HTTP layer fails the way the API can fail. No network, no cost."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        if failure == "no network":
            raise httpx2.ConnectError("connection refused", request=request)
        if failure == "refusal":
            return httpx2.Response(
                200,
                json={
                    "id": "msg_test",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-opus-5-5",
                    "content": [],
                    "stop_reason": "refusal",
                    "stop_sequence": None,
                    "stop_details": {"type": "refusal", "category": None, "explanation": None},
                    "usage": {"input_tokens": 10, "output_tokens": 0},
                },
            )
        status = FAILURES[failure]
        return httpx2.Response(
            status, json={"type": "error", "error": {"type": "api_error", "message": failure}}
        )

    client = anthropic.Anthropic(
        api_key="test-key", max_retries=0, http_client=httpx2.Client(transport=httpx2.MockTransport(handler))
    )
    return ClaudeSummariser(client=client)


# ----------------------------------------------------------------------------- a deliberately wrong model
class HallucinatingSummariser:
    """Test double: adds an event that never happened and overstates the counts.

    The evaluator must catch it; if it ever passes, the evaluator is broken.
    """

    name = "hallucinating"

    def summarise(self, subject_id: str, events: list[dict[str, Any]]) -> SafetyNarrative:
        good = TemplateSummariser().summarise(subject_id, events)
        terms = [*good.event_terms, "Myocardial infarction"]
        return SafetyNarrative(
            subject_id=subject_id,
            total_events=good.total_events + 1,
            serious_events=good.serious_events + 1,
            max_grade=min(good.max_grade + 1, 5),
            event_terms=terms,
            narrative=good.narrative + " A serious myocardial infarction was also reported on day 12.",
        )

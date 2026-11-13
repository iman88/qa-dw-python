"""Narrative service: the GenAI component, exposed over HTTP the way an AI team would ship it.

It does not read the warehouse. The caller sends a subject's adverse event records and gets a
structured safety narrative back. Header ``X-Narrative-Source`` says who wrote it: ``template``,
``claude`` or ``template-fallback`` (Claude was configured but could not answer).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Response
from pydantic import BaseModel, Field

from clinical_dq.genai.summariser import SafetyNarrative, Summariser, TemplateSummariser


class AdverseEventRecord(BaseModel):
    ae_id: str
    meddra_pt: str = Field(min_length=1)
    grade: int = Field(ge=1, le=5)
    is_serious: bool
    onset_date: str | None = None
    outcome: str | None = None


class NarrativeRequest(BaseModel):
    subject_id: str = Field(min_length=1)
    events: list[AdverseEventRecord]


def create_app(summariser: Summariser | None = None) -> FastAPI:
    app = FastAPI(title="Safety Narrative Service", version="0.2.0")
    summariser = summariser or TemplateSummariser()

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "summariser": summariser.name}

    @app.post("/narratives", response_model=SafetyNarrative)
    def narrative(request: NarrativeRequest, response: Response) -> SafetyNarrative:
        events = [e.model_dump() for e in request.events]
        result = summariser.summarise(request.subject_id, events)
        response.headers["X-Narrative-Source"] = getattr(summariser, "last_source", summariser.name)
        return result

    return app

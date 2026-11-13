"""GenAI narrative steps. The narrative service is called over HTTP with Playwright's APIRequestContext."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import uvicorn
from playwright.sync_api import APIRequestContext, Playwright
from pytest_bdd import given, parsers, then, when

from clinical_dq import sql
from clinical_dq.db.client import SqlClient
from clinical_dq.genai.evaluator import EvalResult, evaluate
from clinical_dq.genai.service import create_app
from clinical_dq.genai.summariser import FallbackSummariser, SafetyNarrative
from clinical_dq.reporting.collector import ReportCollector
from tests.support import HallucinatingSummariser, attach, free_port, unavailable_claude


def record(
    collector: ReportCollector, result: EvalResult, output: SafetyNarrative, expected_failure: bool = False
) -> None:
    collector.add_genai(result, expected_failure=expected_failure)
    attach(f"narrative {result.case_id}", {"output": output.model_dump(), "evaluation": result.to_dict()})


@contextmanager
def serve(app: Any) -> Iterator[str]:
    """An extra narrative service for one scenario (for example one whose Claude is failing)."""
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.02)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def summarise_over_http(
    api: APIRequestContext,
    ctx: dict[str, Any],
    collector: ReportCollector,
    subject: dict[str, Any],
    engine: str | None = None,
) -> None:
    ctx["response"] = api.post(
        "/narratives", data={"subject_id": subject["subject_id"], "events": subject["events"]}
    )
    if ctx["response"].status != 200:
        return
    out = SafetyNarrative.model_validate(ctx["response"].json())
    engine = engine or ctx["response"].headers.get("x-narrative-source", "?")
    ctx["output"] = out
    ctx["eval"] = evaluate(subject["subject_id"], engine, subject["subject_id"], subject["events"], out)
    record(collector, ctx["eval"], out)


# ----------------------------------------------------------------------------- the records
@given(parsers.parse('subject "{subject_id}" has these adverse events:'), target_fixture="subject")
def subject_with_events(subject_id: str, datatable: list[list[str]]) -> dict[str, Any]:
    header, *rows = datatable
    events = []
    for row in rows:
        r = dict(zip(header, row, strict=True))
        events.append(
            {
                "ae_id": r["id"],
                "meddra_pt": r["event"],
                "grade": int(r["grade"]),
                "is_serious": r["serious"].lower() == "yes",
                "onset_date": r["onset"],
                "outcome": r["outcome"],
            }
        )
    return {"subject_id": subject_id, "events": events}


@given(parsers.parse('subject "{subject_id}" has no adverse events'), target_fixture="subject")
def subject_without_events(subject_id: str) -> dict[str, Any]:
    return {"subject_id": subject_id, "events": []}


# ----------------------------------------------------------------------------- the service
@when("the narrative service summarises them")
def service_summarises(
    api: APIRequestContext, subject: dict[str, Any], ctx: dict[str, Any], collector: ReportCollector
) -> None:
    summarise_over_http(api, ctx, collector, subject)


@when("I post this narrative request:")
def post_raw(api: APIRequestContext, ctx: dict[str, Any], docstring: str) -> None:
    ctx["response"] = api.post("/narratives", data=json.loads(docstring))


@then(parsers.parse("the response status is {status:d}"))
def response_status(ctx: dict[str, Any], status: int) -> None:
    response = ctx["response"]
    assert response.status == status, f"{response.url} returned {response.status}: {response.text()[:300]}"


@then(parsers.parse('the response header "{header}" is "{value}"'))
def header_is(ctx: dict[str, Any], header: str, value: str) -> None:
    assert ctx["response"].headers.get(header.lower()) == value


@then(parsers.parse('the response header "{header}" is one of "{values}"'))
def header_one_of(ctx: dict[str, Any], header: str, values: str) -> None:
    allowed = {v.strip() for v in values.split(",")}
    value = ctx["response"].headers.get(header.lower())
    assert value in allowed, f"{header}={value!r}, expected one of {sorted(allowed)}"


# ----------------------------------------------------------------------------- what the summary says
@then(parsers.parse("the summary says: total {total:d}, serious {serious:d}, highest grade {grade:d}"))
def summary_counts(ctx: dict[str, Any], total: int, serious: int, grade: int) -> None:
    out: SafetyNarrative = ctx["output"]
    assert (out.total_events, out.serious_events, out.max_grade) == (total, serious, grade), out.model_dump()


@then(parsers.parse('the summary lists exactly these events: "{events}"'))
def summary_terms(ctx: dict[str, Any], events: str) -> None:
    expected = sorted(e.strip() for e in events.split(","))
    assert sorted(ctx["output"].event_terms) == expected


@then(parsers.parse('the narrative mentions "{text}"'))
def narrative_mentions(ctx: dict[str, Any], text: str) -> None:
    assert text.lower() in ctx["output"].narrative.lower(), ctx["output"].narrative


@then("every evaluation metric passes")
def all_metrics_pass(ctx: dict[str, Any]) -> None:
    assert ctx["eval"].passed, ctx["eval"].reasons


# ----------------------------------------------------------------------------- the evaluation itself
@when("a model that invents events summarises them")
def hallucinate(subject: dict[str, Any], collector: ReportCollector, ctx: dict[str, Any]) -> None:
    out = HallucinatingSummariser().summarise(subject["subject_id"], subject["events"])
    ctx["eval"] = evaluate(
        f"{subject['subject_id']} (model that invents events)",
        "invents-events double",
        subject["subject_id"],
        subject["events"],
        out,
    )
    record(collector, ctx["eval"], out, expected_failure=True)


@then("these evaluation metrics fail:")
def metrics_fail(ctx: dict[str, Any], datatable: list[list[str]]) -> None:
    expected = {row[0] for row in datatable[1:]}
    failed = set(ctx["eval"].failed_metrics)
    assert expected <= failed, f"expected {sorted(expected)} to fail, failed: {sorted(failed)}"


@then("these evaluation metrics still pass:")
def metrics_pass(ctx: dict[str, Any], datatable: list[list[str]]) -> None:
    expected = {row[0] for row in datatable[1:]}
    wrongly_failed = expected & set(ctx["eval"].failed_metrics)
    assert not wrongly_failed, f"over-sensitive metrics: {sorted(wrongly_failed)}"


# ----------------------------------------------------------------------------- warehouse subjects
@given(
    parsers.parse('the {n:d} subjects with the most serious adverse events, from "{path}"'),
    target_fixture="subjects",
)
def top_subjects(db: SqlClient, n: int, path: str) -> list[str]:
    return [r["subject_id"] for r in db.query(sql.sql(path), {"limit": n})]


@when(parsers.parse('I send each subject\'s adverse events, from "{path}", to the narrative service'))
def send_subjects(
    api: APIRequestContext, db: SqlClient, ctx: dict[str, Any], subjects: list[str], path: str
) -> None:
    ctx["narratives"] = []
    for subject_id in subjects:
        events = db.query(sql.sql(path), {"subject_id": subject_id})
        response = api.post("/narratives", data={"subject_id": subject_id, "events": events})
        assert response.status == 200, response.text()
        engine = response.headers.get("x-narrative-source", "?")
        ctx["narratives"].append((engine, SafetyNarrative.model_validate(response.json())))


@then(parsers.parse('every narrative passes evaluation against the source records, from "{path}"'))
def narratives_grounded(ctx: dict[str, Any], db: SqlClient, collector: ReportCollector, path: str) -> None:
    failures = []
    for engine, out in ctx["narratives"]:
        events = db.query(sql.sql(path), {"subject_id": out.subject_id})
        result = evaluate(f"warehouse {out.subject_id}", engine, out.subject_id, events, out)
        record(collector, result, out)
        if not result.passed:
            failures.append({out.subject_id: result.reasons})
    assert ctx["narratives"] and not failures, failures


# ----------------------------------------------------------------------------- working without AI
@given(parsers.parse('Claude is configured but fails with "{failure}"'), target_fixture="failing_engine")
def failing_claude(failure: str) -> FallbackSummariser:
    return FallbackSummariser(unavailable_claude(failure))


@when("the narrative service with that Claude summarises them")
def summarise_with_failing_claude(
    playwright: Playwright,
    failing_engine: FallbackSummariser,
    subject: dict[str, Any],
    ctx: dict[str, Any],
    collector: ReportCollector,
) -> None:
    with serve(create_app(failing_engine)) as url:
        api = playwright.request.new_context(base_url=url)
        try:
            summarise_over_http(
                api, ctx, collector, subject, engine=f"fallback after: {failing_engine.last_error}"
            )
        finally:
            api.dispose()

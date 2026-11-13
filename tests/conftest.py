"""Fixtures shared by every feature.

Session scope does the expensive work once: build every layer, start the narrative service
in a background thread and open one Playwright APIRequestContext for it. Mutation scenarios
use their own ``mut_`` schemas and never touch the main build.

Step definitions live in tests/steps/ and are registered in the root conftest.py.
"""

from __future__ import annotations

import os
import re
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest
import uvicorn
from playwright.sync_api import APIRequestContext, Playwright, sync_playwright

from clinical_dq.config import Settings, get_settings
from clinical_dq.db.client import SqlClient, isolated_database
from clinical_dq.etl import pipeline
from clinical_dq.etl.pipeline import BuildReport
from clinical_dq.genai.service import create_app
from clinical_dq.genai.summariser import get_summariser
from clinical_dq.layers import DEFAULT, MUTATION, Layers
from clinical_dq.reporting.collector import ReportCollector
from clinical_dq.results import record_test_results
from clinical_dq.traceability import (
    as_report_rows,
    build_matrix_from_results,
    load_requirements,
    write_matrix,
)
from tests.support import free_port

COLLECTOR = ReportCollector()
AREAS = {
    "data",
    "schema",
    "recon",
    "history",
    "star",
    "partition",
    "warehouse",
    "mutation",
    "genai",
    "incremental",
    "edge",
    "pushdown",
    "monitoring",
    "compliance",
    "genai_scale",
}


# ----------------------------------------------------------------------------- hooks
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if get_settings().genai_provider == "claude":
        return
    skip = pytest.mark.skip(reason="calls Claude for real: set GENAI_PROVIDER=claude to run (costs money)")
    for item in items:
        if "genai_live" in item.keywords:
            item.add_marker(skip)


def pytest_configure(config: pytest.Config) -> None:
    """Requirement tags (@REQ_01 ...) become markers, registered from docs/requirements.json."""
    for req in load_requirements():
        config.addinivalue_line("markers", f"{req['id']}: {req['title']}")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--record-results",
        action="store_true",
        help="store every test outcome in qa_monitor.test_results (flaky-test tracking)",
    )


RESULTS: list[dict] = []


def pytest_sessionstart(session: pytest.Session) -> None:
    if not hasattr(session.config, "workerinput"):  # start each run with no leftover worker parts
        for part_file in (get_settings().reports_dir / "parts").glob("*.json"):
            part_file.unlink()


TRACE: list[dict] = []


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    final = report.when == "call" or (report.when == "setup" and report.outcome != "passed")
    requirements = sorted(k for k in report.keywords if re.fullmatch(r"REQ_\d+", k))
    if final and requirements:
        area = next((k for k in report.keywords if k in AREAS), "")
        TRACE.append(
            {
                "scenario": report.nodeid.split("::")[-1],
                "feature": area,
                "status": report.outcome,
                "requirements": requirements,
            }
        )
    if final:
        RESULTS.append(
            {
                "test_id": report.nodeid,
                "outcome": report.outcome,
                "duration_s": round(report.duration, 3),
                "worker": getattr(report, "node", None) and str(report.node.gateway.id) or "main",
            }
        )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if session.config.getoption("--record-results") and not hasattr(session.config, "workerinput"):
        recorded = record_test_results(SqlClient(get_settings().db_url), RESULTS)
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter:
            reporter.write_line(f"test results recorded: {recorded} rows in qa_monitor.test_results")
    reports = get_settings().reports_dir
    parts = reports / "parts"
    if hasattr(session.config, "workerinput"):  # an xdist worker: save its share, the controller merges
        COLLECTOR.write_part(parts / f"{session.config.workerinput['workerid']}.json")
        return
    if parts.exists():
        COLLECTOR.merge_parts(parts)
        for part_file in parts.glob("*.json"):
            part_file.unlink()
    if TRACE:  # pytest's own results reach the controller from every xdist worker
        matrix = build_matrix_from_results(TRACE)
        write_matrix(matrix, reports)
        COLLECTOR.requirements = as_report_rows(matrix)
    path = COLLECTOR.write(reports)
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if path and reporter:
        reporter.write_line(f"data quality report: {path}")


# ----------------------------------------------------------------------------- database
@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest.fixture(scope="session")
def db(settings: Settings) -> Iterator[SqlClient]:
    """The database for this test process.

    Under pytest-xdist every worker gets its own database (clinical_gw0, clinical_gw1, ...), and a CI run
    can set TEST_RUN_ID to get its own throwaway database too. Inline SQL in the features can therefore
    keep plain schema names: no worker or run ever touches another one's tables.
    """
    url = settings.db_url
    suffix = "_".join(s for s in (os.getenv("TEST_RUN_ID"), os.getenv("PYTEST_XDIST_WORKER")) if s)
    try:
        SqlClient(url).wait_until_ready(timeout_s=30)
        if suffix:
            url = isolated_database(url, suffix)
    except RuntimeError as exc:
        pytest.exit(str(exc), returncode=3)
    client = SqlClient(url)
    yield client
    client.dispose()


@pytest.fixture(scope="session")
def build(db: SqlClient, settings: Settings) -> BuildReport:
    report = pipeline.run(db, DEFAULT, settings.data_seed, settings.subjects_per_study)
    COLLECTOR.build = {"stats": report.stats, "timings_ms": report.timings_ms}
    return report


@pytest.fixture(scope="session")
def mutation_layers(db: SqlClient) -> Iterator[Layers]:
    yield MUTATION
    pipeline.drop(db, MUTATION)


@pytest.fixture(scope="session")
def collector() -> ReportCollector:
    return COLLECTOR


@pytest.fixture
def ctx() -> dict[str, Any]:
    """Per-scenario scratch space shared between steps."""
    return {}


# ----------------------------------------------------------------------------- narrative service
@pytest.fixture(scope="session")
def narrative_service_url(settings: Settings) -> Iterator[str]:
    app = create_app(get_summariser(settings.genai_provider, settings.claude_model, settings.genai_fallback))
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("Narrative service did not start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def playwright() -> Iterator[Playwright]:
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def api(playwright: Playwright, narrative_service_url: str) -> Iterator[APIRequestContext]:
    """Playwright's HTTP client. No browser is started; this is API testing only."""
    context = playwright.request.new_context(
        base_url=narrative_service_url, extra_http_headers={"Accept": "application/json"}
    )
    yield context
    context.dispose()

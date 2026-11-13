"""Steps for 13_production_monitoring.feature: monitor runs, stored results and webhook alerts."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest
from pytest_bdd import given, parsers, then, when

from clinical_dq import monitor, sql
from clinical_dq.db.client import SqlClient
from clinical_dq.layers import DEFAULT, Layers
from tests.support import attach, free_port


@pytest.fixture
def webhook() -> Iterator[dict[str, Any]]:
    """A local HTTP endpoint standing in for Slack, Teams or an on-call tool."""
    received: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - http.server naming
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.append(json.loads(body))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args: Any) -> None:
            pass

    server = HTTPServer(("127.0.0.1", free_port()), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield {"url": f"http://127.0.0.1:{server.server_port}/alerts", "received": received}
    server.shutdown()


@given("a webhook that records the alerts it receives")
def webhook_ready(webhook: dict[str, Any]) -> None:
    assert webhook["received"] == []


def _run(db: SqlClient, ctx: dict[str, Any], webhook: dict[str, Any], layers: Layers, as_of: str) -> None:
    ctx["run"] = monitor.run(db, datetime.fromisoformat(as_of), layers, webhook=webhook["url"])
    attach("monitor run failures", [vars(o) for o in ctx["run"].failures])


@when(parsers.parse('the monitor runs as of "{as_of}"'))
def monitor_main(db: SqlClient, ctx: dict[str, Any], webhook: dict[str, Any], as_of: str) -> None:
    _run(db, ctx, webhook, DEFAULT, as_of)


@when(parsers.parse('the incident "{path}" happens on the copy'))
def incident(db: SqlClient, mutation_layers: Layers, path: str) -> None:
    assert db.execute(sql.sql(path, mutation_layers)) > 0, f"{path} changed nothing"


@when(parsers.parse('the monitor runs on the copy as of "{as_of}"'))
def monitor_copy(
    db: SqlClient, ctx: dict[str, Any], webhook: dict[str, Any], mutation_layers: Layers, as_of: str
) -> None:
    _run(db, ctx, webhook, mutation_layers, as_of)


@then("every check of the run passed")
def all_passed(ctx: dict[str, Any]) -> None:
    assert not ctx["run"].failures, [(f.check_id, f.sample[:2]) for f in ctx["run"].failures]


@then("the run stored a result for every check, including these monitoring checks:")
def results_stored(db: SqlClient, ctx: dict[str, Any], datatable: list[list[str]]) -> None:
    stored = db.query(sql.load("sql/results/run_results.sql"), {"run_id": ctx["run"].run_id})
    assert len(stored) == len(ctx["run"].outcomes) > 80
    ids = {r["check_id"] for r in stored}
    missing = [row[0] for row in datatable[1:] if row[0] not in ids]
    assert not missing, missing


@then("no alert was sent")
def no_alert(ctx: dict[str, Any], webhook: dict[str, Any]) -> None:
    assert not ctx["run"].alert_sent and webhook["received"] == []


@then(parsers.parse('the check "{check}" failed in the run'))
def check_failed(ctx: dict[str, Any], check: str) -> None:
    failed = [f.check_id for f in ctx["run"].failures]
    assert check in failed, failed


@then(parsers.parse('one alert was sent, naming "{check}"'))
def alert_sent(webhook: dict[str, Any], check: str) -> None:
    assert len(webhook["received"]) == 1, webhook["received"]
    assert check in [f["check"] for f in webhook["received"][0]["failures"]]

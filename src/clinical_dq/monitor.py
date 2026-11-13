"""Production monitoring: the same checks as the test suite, run on a schedule against live data.

A run executes every data quality rule, every reconciliation (push-down), every schema contract and
the monitoring checks in sql/checks/monitoring/ (freshness, volume, drift). Each result is stored in
qa_monitor.check_results, so trends and audits are a SQL query away. If anything fails and a webhook
is configured (ALERT_WEBHOOK_URL, for example a Slack or Teams incoming webhook or an on-call tool),
one alert with every failure is posted to it.

    clinical-dq monitor --as-of "2026-06-30 23:59+00"
"""

from __future__ import annotations

import json
import logging
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any

from clinical_dq import sql
from clinical_dq.db.client import SqlClient
from clinical_dq.dq import checks as dq
from clinical_dq.dq import schema
from clinical_dq.layers import DEFAULT, Layers
from clinical_dq.recon import checks as recon

log = logging.getLogger("clinical_dq.monitor")
MONITORING = "sql/checks/monitoring"
STORE = "sql/results/results_table.sql"


@dataclass(frozen=True)
class Monitor:
    file: str
    layer: str
    params: dict[str, Any]

    @property
    def id(self) -> str:
        target = ".".join(p for p in (self.layer, self.params.get("table", "")) if p)
        return f"{self.file} on {target}"


MONITORS = [
    Monitor(f"{MONITORING}/freshness.sql", "raw", {"table": "visit_events", "max_hours": 72}),
    Monitor(f"{MONITORING}/freshness.sql", "raw", {"table": "adverse_event_events", "max_hours": 168}),
    Monitor(
        f"{MONITORING}/period_volume.sql", "raw", {"table": "visit_events", "days": 28, "min_ratio": 0.25}
    ),
    Monitor(
        f"{MONITORING}/period_volume.sql",
        "raw",
        {"table": "adverse_event_events", "days": 28, "min_ratio": 0.25},
    ),
    Monitor(f"{MONITORING}/grade_drift.sql", "dwh", {"days": 90, "max_psi": 0.25}),
]


@dataclass
class CheckOutcome:
    check_id: str
    kind: str
    passed: bool
    offending_rows: int
    sample: list[Any] = field(default_factory=list)


@dataclass
class MonitorRun:
    run_id: str
    as_of: datetime
    outcomes: list[CheckOutcome]
    alert_sent: bool = False

    @property
    def failures(self) -> list[CheckOutcome]:
        return [o for o in self.outcomes if not o.passed]


def run_monitor_check(db: SqlClient, monitor: Monitor, layers: Layers, as_of: datetime) -> CheckOutcome:
    query = sql.sql(monitor.file, layers, **monitor.params)
    rows = db.query(query, {"as_of": as_of})
    return CheckOutcome(monitor.id, PurePosixPath(monitor.file).stem, not rows, len(rows), rows[:5])


def send_alert(url: str, run: MonitorRun) -> None:
    body = {
        "text": f"Data quality: {len(run.failures)} failing checks in run {run.run_id} (as of {run.as_of:%Y-%m-%d %H:%M})",
        "run_id": run.run_id,
        "failures": [
            {"check": f.check_id, "kind": f.kind, "offending_rows": f.offending_rows, "sample": f.sample[:3]}
            for f in run.failures
        ],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body, default=str).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - URL comes from configuration
        response.read()


def run(db: SqlClient, as_of: datetime, layers: Layers = DEFAULT, webhook: str | None = None) -> MonitorRun:
    outcomes = [
        CheckOutcome(r.name, "rule", r.passed, r.failing_rows, r.sample[:5]) for r in dq.run_all(db, layers)
    ]
    outcomes += [
        CheckOutcome(
            r.name,
            "reconciliation",
            r.passed,
            len(r.missing_in_target) + len(r.extra_in_target) + len(r.mismatches),
            r.mismatches[:5],
        )
        for r in recon.run_all(db, layers, engine="pushdown")
    ]
    outcomes += [
        CheckOutcome(r.name, "contract", r.passed, r.failing_rows, r.sample[:5])
        for r in schema.run_all(db, layers)
    ]
    outcomes += [run_monitor_check(db, m, layers, as_of) for m in MONITORS]

    result = MonitorRun(f"run-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}", as_of, outcomes)
    db.execute_script(sql.load(STORE))
    ran_at = datetime.now(UTC)
    db.insert_many(
        "qa_monitor.check_results",
        [
            {
                "run_id": result.run_id,
                "ran_at": ran_at,
                "as_of": as_of,
                "target": layers.prefix or "main",
                "check_id": o.check_id,
                "kind": o.kind,
                "passed": o.passed,
                "offending_rows": o.offending_rows,
                "sample": json.dumps(o.sample, default=str),
            }
            for o in outcomes
        ],
    )
    if result.failures and webhook:
        send_alert(webhook, result)
        result.alert_sent = True
    log.info("monitor run %s: %d checks, %d failing", result.run_id, len(outcomes), len(result.failures))
    return result

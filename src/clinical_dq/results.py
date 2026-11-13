"""Test outcomes stored in the database: one row per test per run (pytest --record-results).

With history in a table, flaky tests are a query (sql/queries/quality/flaky_tests.sql) instead of a
feeling, and slow tests or trends are one GROUP BY away.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from clinical_dq import sql
from clinical_dq.db.client import SqlClient

TABLE = "sql/results/test_results_table.sql"
FLAKY = "sql/queries/quality/flaky_tests.sql"


def record_test_results(db: SqlClient, results: list[dict[str, Any]], run_id: str | None = None) -> int:
    db.execute_script(sql.load(TABLE))
    run_id = run_id or f"tests-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"
    ran_at = datetime.now(UTC)
    return db.insert_many(
        "qa_monitor.test_results", [{"run_id": run_id, "ran_at": ran_at, **r} for r in results]
    )


def flaky_tests(db: SqlClient, runs: int = 20) -> list[dict[str, Any]]:
    db.execute_script(sql.load(TABLE))
    return db.query(sql.load(FLAKY), {"runs": runs})

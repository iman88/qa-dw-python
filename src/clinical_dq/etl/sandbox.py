"""A tiny CDC sandbox for hand-built edge cases and property-based tests.

It lands visit events you write yourself into one plain raw table and runs the *real* history and
latest SQL from sql/build/ and sql/incremental/ for the visit entity only. Rebuilding takes a few
milliseconds, so hundreds of generated feeds can be checked in one run.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from clinical_dq import sql
from clinical_dq.data.entities import VISIT
from clinical_dq.db.client import SqlClient
from clinical_dq.etl.pipeline import entity_params
from clinical_dq.layers import Layers

LANDING = "sql/fixtures/visit_landing.sql"
FULL = [
    "sql/build/history/10_hist_schema.sql",
    "sql/build/history/11_hist_entity.sql",
    "sql/build/history/12_hist_current_view_entity.sql",
    "sql/build/latest/20_latest_schema.sql",
    "sql/build/latest/21_latest_entity.sql",
]
INCREMENTAL = [
    "sql/incremental/history/61_hist_append_entity.sql",
    "sql/incremental/latest/62_latest_merge_entity.sql",
]
DEFAULTS = {
    "subject_id": "SUBJ-0001",
    "visit_type": "BASELINE",
    "visit_date": "2025-03-01",
    "status": "SCHEDULED",
}


@dataclass
class Sandbox:
    db: SqlClient
    layers: Layers

    def _run(self, paths: list[str], **extra: Any) -> None:
        script = "\n".join(sql.sql(p, self.layers, **entity_params(VISIT), **extra) for p in paths)
        self.db.execute_script(script)

    def reset(self) -> None:
        self.db.execute_script(sql.sql(LANDING, self.layers))

    def land(self, events: list[dict[str, Any]]) -> None:
        rows = [{**DEFAULTS, **e, "batch_id": e.get("batch_id", "fixture")} for e in events]
        self.db.insert_many(f"{self.layers.raw}.visit_events", rows)

    def build(self) -> None:
        """History and latest from everything landed so far, exactly as the full build does it."""
        self._run(FULL)

    def increment(self, batch_start: datetime) -> None:
        """Fold events ingested from ``batch_start`` into the existing history and latest."""
        self._run(INCREMENTAL, batch_start=batch_start.isoformat(sep=" "))

    def history(self) -> list[dict[str, Any]]:
        return self.db.query(
            f"SELECT visit_id, change_seq, op, status, valid_from, valid_to, is_current, is_deleted "
            f"FROM {self.layers.hist}.visit_history ORDER BY visit_id, change_seq"
        )

    def latest(self) -> list[dict[str, Any]]:
        return self.db.query(
            f"SELECT visit_id, status, last_change_seq FROM {self.layers.latest}.visit ORDER BY visit_id"
        )

    def drop(self) -> None:
        self.db.execute_script(
            "\n".join(
                f"DROP SCHEMA IF EXISTS {s} CASCADE;"
                for s in (self.layers.raw, self.layers.hist, self.layers.latest)
            )
        )

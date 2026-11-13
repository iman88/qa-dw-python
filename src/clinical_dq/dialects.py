"""Running the same SQL on BigQuery.

Every file under sql/ is in one of three states for BigQuery:

* counterpart: a hand-written file at sql/dialects/bigquery/<same path> (DDL, partitioning, catalog
  queries, checksums: where BigQuery differs and a translation would be wrong or slow);
* portable:    no Postgres-only feature, so sqlglot transpiles it (bind :name becomes @name);
* not needed:  listed in sql/dialects/bigquery/manifest.json with the reason (test harness,
  access control done with IAM, value scanning done with Cloud DLP).

`check_coverage` proves every file is in one of these states, so nothing is silently Postgres-only.
"""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel

from clinical_dq import sql
from clinical_dq.layers import DEFAULT, Layers

DIALECT_ROOT = sql.SQL_ROOT / "dialects" / "bigquery"
POSTGRES_ONLY = re.compile(
    r"DO \$\$|pg_catalog|pg_class|pg_inherits|pg_namespace|tableoid|hashtextextended|query_to_xml|SET TIME ZONE|"
    r"DETACH PARTITION|PARTITION BY RANGE|PARTITION OF|relkind|format_type|pg_get_|regclass|CREATE ROLE|GRANT |"
    r"LIKE \{src\}|generate_series|DISTINCT ON|serial PRIMARY|ALTER COLUMN|percentile_cont|information_schema|"
    r"REFERENCES|CHECK \(|IS DISTINCT FROM \(|UPDATE .* FROM|MERGE INTO",
    re.IGNORECASE,
)
SAMPLE_PARAMS: dict[str, Any] = {
    "schema": "dwh",
    "table": "fact_adverse_event",
    "fact": "fact_adverse_event",
    "fk": "subject_sk",
    "dim": "dim_subject",
    "pk": "subject_sk",
    "column": "grade",
    "values": "1, 2",
    "condition": "grade IS NULL",
    "first_month": "2025-01-01",
    "last_month": "2026-12-01",
    "approved": "'dim_site.investigator'",
    "date_column": "onset_date",
    "date_key_column": "onset_date_key",
    "partition_name": "p",
    "query": "SELECT 'x' AS ae_id, 1 AS grade",
    "key_expr": "q.ae_id",
    "row_expr": "q.ae_id",
    "buckets": 64,
    "max_hours": 72,
    "days": 28,
    "min_ratio": 0.25,
    "max_psi": 0.25,
    "max_gb": 10,
    "batch_start": "2026-01-01 00:00:00+00",
    "entity": "visit",
    "key": "visit_id",
    "columns": "visit_id, subject_id, visit_type, visit_date, status",
    "events_table": "visit_events",
    "history_table": "visit_history",
    "raw_columns": "r.visit_id, r.subject_id, r.visit_type, r.visit_date, r.status",
    "source_columns": "s.visit_id, s.subject_id, s.visit_type, s.visit_date, s.status",
    "set_columns": "subject_id = s.subject_id, status = s.status",
}


@cache
def manifest() -> dict[str, str]:
    return json.loads((DIALECT_ROOT / "manifest.json").read_text(encoding="utf-8"))["not_needed"]


def counterpart(path: str) -> Path | None:
    candidate = DIALECT_ROOT / path.removeprefix("sql/")
    return candidate if candidate.exists() else None


def not_needed_reason(path: str) -> str | None:
    return next((reason for prefix, reason in manifest().items() if path.startswith(prefix)), None)


def to_bigquery(text: str) -> str:
    """Transpile one rendered Postgres statement list to BigQuery; refuses anything it cannot translate."""
    text = re.sub(r"(?<!:):([a-zA-Z_]\w*)", r"@\1", text)
    statements = sqlglot.parse(text, read="postgres", error_level=ErrorLevel.RAISE)
    if any(isinstance(s, exp.Command) for s in statements if s is not None):
        raise ValueError("contains a statement sqlglot cannot translate (kept as an opaque command)")
    return ";\n".join(
        s.sql(dialect="bigquery", pretty=True, unsupported_level=ErrorLevel.RAISE)
        for s in statements
        if s is not None
    )


def classify(path: str) -> tuple[str, str]:
    """(state, detail) for one file: counterpart, portable, not needed, or missing."""
    if counterpart(path):
        return "counterpart", str(counterpart(path))
    reason = not_needed_reason(path)
    if reason:
        return "not needed", reason
    text = sql.load(path)
    code = "\n".join(line for line in text.splitlines() if not line.strip().startswith("--"))
    found = POSTGRES_ONLY.search(code)
    if found:
        return "missing", f"uses {found.group(0)!r} and has no BigQuery counterpart"
    try:
        to_bigquery(sql.render(text, DEFAULT, **SAMPLE_PARAMS))
    except Exception as exc:  # noqa: BLE001 - any translation failure means the file needs a counterpart
        return "missing", f"does not transpile: {str(exc).splitlines()[0][:120]}"
    return "portable", ""


def all_files() -> list[str]:
    return [
        f"sql/{p.relative_to(sql.SQL_ROOT).as_posix()}"
        for p in sorted(sql.SQL_ROOT.rglob("*.sql"))
        if "dialects" not in p.parts
    ]


def check_coverage() -> dict[str, list[str]]:
    report: dict[str, list[str]] = {"counterpart": [], "portable": [], "not needed": [], "missing": []}
    for path in all_files():
        state, detail = classify(path)
        report[state].append(path if state != "missing" else f"{path}: {detail}")
    return report


def bigquery_sql(path: str, layers: Layers = DEFAULT, **identifiers: Any) -> str:
    """The BigQuery SQL for a repo SQL file: its counterpart, or the transpiled Postgres file."""
    own = counterpart(path)
    if own:
        return sql.render(own.read_text(encoding="utf-8"), layers, **identifiers)
    return to_bigquery(sql.sql(path, layers, **identifiers))

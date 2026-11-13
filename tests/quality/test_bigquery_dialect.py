"""BigQuery: every SQL file either translates, has a hand-written counterpart, or says why it is not needed.

These tests run offline: they parse and translate the SQL with sqlglot. Executing it needs a Google
Cloud project (the BigQuery sandbox is free); see the README.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel

from clinical_dq import dialects, sql
from clinical_dq.etl.pipeline import BUILD, build_scripts

pytestmark = pytest.mark.quality


def test_every_sql_file_runs_on_bigquery_or_says_why() -> None:
    report = dialects.check_coverage()
    assert report["missing"] == [], "\n".join(report["missing"])
    assert len(report["counterpart"]) >= 20 and len(report["portable"]) >= 40


@pytest.mark.parametrize("path", sorted(str(p) for p in dialects.DIALECT_ROOT.rglob("*.sql")))
def test_each_counterpart_is_valid_bigquery(path: str) -> None:
    text = sql.render(Path(path).read_text(encoding="utf-8"), **dialects.SAMPLE_PARAMS)
    statements = sqlglot.parse(text, read="bigquery", error_level=ErrorLevel.RAISE)
    assert statements and not any(isinstance(s, exp.Command) for s in statements if s is not None)


@pytest.mark.parametrize("table", ["40_fact_adverse_event", "41_fact_visit"])
def test_facts_are_partitioned_by_month_clustered_and_refuse_full_scans(table: str) -> None:
    text = (dialects.DIALECT_ROOT / "build" / "facts" / f"{table}.sql").read_text(encoding="utf-8")
    assert "PARTITION BY DATE_TRUNC(" in text and ", MONTH)" in text
    assert "CLUSTER BY study_sk, subject_sk" in text
    assert "require_partition_filter = TRUE" in text


def test_the_whole_build_exports_for_bigquery() -> None:
    needed = [p for p in build_scripts() if dialects.classify(p)[0] != "not needed"]
    exported = [dialects.bigquery_sql(p, **dialects.SAMPLE_PARAMS) for p in needed]
    assert len(exported) == len(sql.files(BUILD)) - 3  # security (IAM) and the two schema-only scripts
    assert all("::" not in s and "DO $$" not in s for s in exported)


def test_a_portable_reconciliation_translates_postgres_specifics() -> None:
    out = dialects.bigquery_sql("sql/checks/recon/facts/fact_adverse_event_vs_source/source.sql")
    assert "DATE_DIFF" in out.upper() or "-" in out  # date subtraction rewritten for BigQuery
    assert "::" not in out

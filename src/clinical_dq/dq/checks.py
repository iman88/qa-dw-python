"""Data quality checks: one SQL file per rule type, returning the *offending* rows (zero rows = pass).

A check is a rule file plus the layer and identifiers it runs on, for example
``sql/checks/rules/keys/referential_integrity.sql`` on ``dwh.fact_adverse_event.subject_sk``.
Its id is ``<file> on <target>`` and its description is the first comment line of the file.
Feature files call the rule files directly with a data table of identifiers; this catalogue
lets the CLI and the mutation tests run every check without a feature file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from clinical_dq import sql
from clinical_dq.data.entities import ENTITIES
from clinical_dq.db.client import SqlClient
from clinical_dq.layers import DEFAULT, Layers

SAMPLE = 10
RULES = "sql/checks/rules"
FACT_MONTHS = {"first_month": "2025-01-01", "last_month": "2026-12-01"}
RAW_MONTHS = {"first_month": "2024-12-01", "last_month": "2026-12-01"}
# Personal data the warehouse may hold on purpose (investigator names), each protected by column-level
# access in sql/build/security/. Anything else that looks personal is a finding.
APPROVED_PERSONAL_DATA = (
    "'dim_site.investigator', 'v_site_current.investigator', 'v_adverse_event_detail.investigator_at_onset'"
)


def target_of(layer: str, params: dict[str, Any]) -> str:
    """Human-readable target, e.g. dwh.fact_adverse_event.subject_sk or latest.adverse_event (ae_id)."""
    table = params.get("fact") or params.get("table") or params.get("entity") or ""
    column = params.get("fk") or params.get("column") or ""
    target = ".".join(p for p in (layer, table, column) if p)
    if params.get("columns"):
        target += f" ({params['columns']})"
    return target


@dataclass(frozen=True)
class DqCheck:
    file: str  # repo-relative, e.g. sql/checks/rules/keys/unique.sql
    layer: str
    params: dict[str, str] = field(default_factory=dict)

    @property
    def target(self) -> str:
        return target_of(self.layer, self.params) if self.params else f"{self.layer}"

    @property
    def id(self) -> str:
        return f"{self.file} on {self.target}"

    @property
    def rule(self) -> str:
        return PurePosixPath(self.file).stem

    @property
    def description(self) -> str:
        return sql.description(self.file, **self.params)

    def render(self, layers: Layers = DEFAULT) -> str:
        return sql.sql(self.file, layers, schema="{" + self.layer + "}", **self.params)


@dataclass
class DqResult:
    name: str
    layer: str
    description: str
    failing_rows: int
    sample: list[dict[str, Any]] = field(default_factory=list)
    sql: str = ""

    @property
    def passed(self) -> bool:
        return self.failing_rows == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "layer": self.layer,
            "description": self.description,
            "passed": self.passed,
            "failing_rows": self.failing_rows,
            "sample": [{k: str(v) for k, v in row.items()} for row in self.sample],
            "sql": self.sql,
        }


RULE_FILES = {PurePosixPath(p).stem: p for p in sql.files(RULES)}  # rule name -> file in its category


def check(rule: str, layer: str, **params: str) -> DqCheck:
    return DqCheck(RULE_FILES[rule], layer, dict(params))


def catalogue() -> list[DqCheck]:
    c: list[DqCheck] = []
    for e in ENTITIES:
        c += [
            check("unique", "latest", table=e.name, columns=e.key),
            check("unique", "hist", table=e.history_table, columns="change_seq"),
            check("scd2_no_overlap", "hist", table=e.history_table, key=e.key),
            check("scd2_single_current", "hist", table=e.history_table, key=e.key),
            check("deletes_applied", "latest", entity=e.name, key=e.key, history_table=e.history_table),
            check("default_partition_empty", "raw", table=e.events_table),
            check("partition_plan", "raw", table=e.events_table, **RAW_MONTHS),
        ]
    for table, columns in [
        ("dim_study", "study_id"),
        ("dim_subject", "subject_id"),
        ("dim_site", "site_id, valid_from"),
        ("fact_adverse_event", "ae_id"),
        ("fact_visit", "visit_id"),
        ("v_adverse_event_detail", "ae_id"),
        ("v_safety_by_study_month", "study_id, year_month"),
    ]:
        c.append(check("unique", "dwh", table=table, columns=columns))
    c += [
        check("scd2_no_overlap", "dwh", table="dim_site", key="site_id"),
        check("scd2_single_current", "dwh", table="dim_site", key="site_id"),
    ]
    for fact, fk, dim, pk in [
        ("fact_adverse_event", "subject_sk", "dim_subject", "subject_sk"),
        ("fact_adverse_event", "study_sk", "dim_study", "study_sk"),
        ("fact_adverse_event", "site_sk", "dim_site", "site_sk"),
        ("fact_adverse_event", "onset_date_key", "dim_date", "date_key"),
        ("fact_visit", "subject_sk", "dim_subject", "subject_sk"),
        ("fact_visit", "study_sk", "dim_study", "study_sk"),
        ("fact_visit", "visit_date_key", "dim_date", "date_key"),
    ]:
        c.append(check("referential_integrity", "dwh", fact=fact, fk=fk, dim=dim, pk=pk))
    c += [
        check("accepted_values", "dwh", table="fact_adverse_event", column="grade", values="1, 2, 3, 4, 5"),
        check(
            "accepted_values",
            "dwh",
            table="dim_subject",
            column="arm",
            values="'PLACEBO', 'DOSE_LOW', 'DOSE_HIGH'",
        ),
        check(
            "not_null",
            "dwh",
            table="fact_adverse_event",
            condition="meddra_pt IS NULL OR soc IS NULL OR grade IS NULL OR is_serious IS NULL OR onset_date IS NULL",
        ),
        check("default_partition_empty", "dwh", table="fact_adverse_event"),
        check("default_partition_empty", "dwh", table="fact_visit"),
        check("partition_plan", "dwh", table="fact_adverse_event", **FACT_MONTHS),
        check("partition_plan", "dwh", table="fact_visit", **FACT_MONTHS),
        check("scd2_point_in_time_site", "dwh"),
        check("personal_data_columns", "dwh", approved=APPROVED_PERSONAL_DATA),
        check("personal_data_values", "dwh"),
        check(
            "date_key_matches_partition_date",
            "dwh",
            table="fact_adverse_event",
            date_column="onset_date",
            date_key_column="onset_date_key",
        ),
        check(
            "date_key_matches_partition_date",
            "dwh",
            table="fact_visit",
            date_column="visit_date",
            date_key_column="visit_date_key",
        ),
    ]
    return c


BY_ID = {c.id: c for c in catalogue()}


def run_check(db: SqlClient, chk: DqCheck, layers: Layers = DEFAULT) -> DqResult:
    query = chk.render(layers)
    rows = db.query(query)
    return DqResult(chk.id, chk.layer, chk.description, len(rows), rows[:SAMPLE], " ".join(query.split()))


def run_all(db: SqlClient, layers: Layers = DEFAULT) -> list[DqResult]:
    return [run_check(db, c, layers) for c in catalogue()]


# --------------------------------------------------------------------- partition pruning
_PARTITION = re.compile(r"on (?:\w+\.)?(\w+?_(?:\d{6}|default))\b")


def partitions_scanned(db: SqlClient, query: str, params: dict[str, Any] | None = None) -> list[str]:
    """Partitions the planner reads for ``query`` (already rendered), taken from EXPLAIN."""
    plan = db.explain(query, params)
    return sorted(set(_PARTITION.findall(plan)))

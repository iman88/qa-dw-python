"""Reconciliations: compare ``source.sql`` with ``target.sql`` in a folder, by business key.

A check is identified by its folder, e.g. ``sql/checks/recon/facts/fact_adverse_event_vs_source``.
Folders whose SQL uses {entity} (latest/, history/) are templates run once per entity and
identified as ``<folder> for <entity>``. The description is the first comment line of ``source.sql``.

The feature file names the folder and the key directly; this catalogue lets the CLI and the
mutation tests run every reconciliation without a feature file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from clinical_dq import sql
from clinical_dq.data.entities import BY_NAME as ENTITY
from clinical_dq.data.entities import ENTITIES
from clinical_dq.db.client import SqlClient
from clinical_dq.etl.pipeline import entity_params
from clinical_dq.layers import DEFAULT, Layers
from clinical_dq.recon import pushdown
from clinical_dq.recon.engine import ReconResult, diff_rows

ROOT = "sql/checks/recon"


@dataclass(frozen=True)
class ReconCheck:
    folder: str  # repo-relative, e.g. sql/checks/recon/facts/fact_adverse_event_vs_source
    key: tuple[str, ...]
    entity: str | None = None
    params: dict[str, str] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return f"{self.folder} for {self.entity}" if self.entity else self.folder

    @property
    def description(self) -> str:
        return sql.description(f"{self.folder}/source.sql", **self.params)

    def source_sql(self, layers: Layers = DEFAULT) -> str:
        return sql.sql(f"{self.folder}/source.sql", layers, **self.params)

    def target_sql(self, layers: Layers = DEFAULT) -> str:
        return sql.sql(f"{self.folder}/target.sql", layers, **self.params)


def make(folder: str, key: str | tuple[str, ...], entity: str | None = None) -> ReconCheck:
    keys = tuple(k.strip() for k in key.split(",")) if isinstance(key, str) else key
    params = entity_params(ENTITY[entity]) if entity else {}
    return ReconCheck(folder.replace("\\", "/"), keys, entity, params)


def _catalogue() -> list[ReconCheck]:
    checks: list[ReconCheck] = []
    for e in ENTITIES:
        checks.append(make(f"{ROOT}/latest/latest_vs_source", e.key, e.name))
        checks.append(make(f"{ROOT}/history/hist_vs_raw_changes", "change_seq", e.name))
        checks.append(make(f"{ROOT}/history/hist_current_vs_latest", e.key, e.name))
    checks += [
        make(f"{ROOT}/dimensions/dim_subject_vs_source", "subject_id"),
        make(f"{ROOT}/facts/fact_adverse_event_vs_source", "ae_id"),
        make(f"{ROOT}/facts/fact_visit_vs_source", "visit_id"),
        make(f"{ROOT}/aggregates/safety_totals_by_study", "study_id"),
        make(f"{ROOT}/aggregates/visits_by_study_month", "study_id, year_month"),
        make(f"{ROOT}/views/v_adverse_event_detail_vs_source", "ae_id"),
        make(f"{ROOT}/views/v_safety_by_study_month_vs_source", "study_id, year_month"),
        make(f"{ROOT}/views/v_site_current_vs_source", "site_id"),
    ]
    return checks


CHECKS: list[ReconCheck] = _catalogue()
BY_ID = {c.id: c for c in CHECKS}


ENGINES = ("pushdown", "full")


def run_check(
    db: SqlClient, check: ReconCheck, layers: Layers = DEFAULT, engine: str | None = None, buckets: int = 64
) -> ReconResult:
    """``pushdown`` (default): checksums in the database, fetch only differing buckets.
    ``full``: fetch every row of both sides and compare in Python (the reference behaviour)."""
    engine = engine or os.getenv("RECON_ENGINE", "pushdown")
    if engine == "pushdown":
        return pushdown.reconcile(
            db,
            check.id,
            check.source_sql(layers),
            check.target_sql(layers),
            check.key,
            buckets=buckets,
            description=check.description,
        )
    if engine != "full":
        raise ValueError(f"RECON_ENGINE must be one of {ENGINES}, not {engine!r}")
    source = db.query(check.source_sql(layers))
    target = db.query(check.target_sql(layers))
    result = diff_rows(check.id, source, target, check.key, description=check.description)
    result.stats = {
        "engine": "full",
        "rows_fetched": len(source) + len(target),
        "rows_total": len(source) + len(target),
    }
    return result


def run_all(db: SqlClient, layers: Layers = DEFAULT, engine: str | None = None) -> list[ReconResult]:
    return [run_check(db, c, layers, engine) for c in CHECKS]

"""Defect injection steps: break a separate copy of every layer and prove the right check notices."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pytest_bdd import given, parsers, then, when

from clinical_dq import sql
from clinical_dq.config import Settings
from clinical_dq.db.client import SqlClient
from clinical_dq.dq import checks as dq
from clinical_dq.dq import schema
from clinical_dq.etl import defects, pipeline
from clinical_dq.layers import Layers
from clinical_dq.reporting.collector import ReportCollector
from tests.support import attach

FEATURES = Path(__file__).parents[1] / "features"


@given('a fresh copy of every layer, in schemas prefixed "mut_"')
def fresh_copy(db: SqlClient, settings: Settings, mutation_layers: Layers) -> None:
    pipeline.run(db, mutation_layers, settings.data_seed, settings.subjects_per_study)


@when(parsers.parse('I apply the defect "{path}"'))
def apply_defect(db: SqlClient, mutation_layers: Layers, ctx: dict[str, Any], path: str) -> None:
    assert path in defects.BY_PATH, f"no defect script at {path}"
    ctx["defect"] = defects.BY_PATH[path]
    defects.inject(db, mutation_layers, path)


@when("I run every reconciliation, check and contract on the copy")
def run_everything(db: SqlClient, mutation_layers: Layers, ctx: dict[str, Any]) -> None:
    from clinical_dq.recon import checks as recon

    results = recon.run_all(db, mutation_layers) + dq.run_all(db, mutation_layers)
    results += schema.run_all(db, mutation_layers)
    ctx["failed"] = sorted(r.name for r in results if not r.passed)
    attach("checks that fired", ctx["failed"])


def _expect_failure(ctx: dict[str, Any], collector: ReportCollector, check_id: str) -> None:
    caught = check_id in ctx["failed"]
    defect = ctx["defect"]
    collector.add_mutation(defect.path, defect.story, check_id, caught, ctx["failed"])
    assert caught, f"{defect.path} was not caught by {check_id}; checks that fired: {ctx['failed']}"


@then(parsers.parse('the reconciliation "{folder}" fails'))
def recon_fails(ctx: dict[str, Any], collector: ReportCollector, folder: str) -> None:
    sql.resolve(folder)  # the folder must exist
    _expect_failure(ctx, collector, folder)


@then(parsers.parse('the reconciliation "{folder}" for entity "{entity}" fails'))
def recon_entity_fails(ctx: dict[str, Any], collector: ReportCollector, folder: str, entity: str) -> None:
    sql.resolve(folder)
    _expect_failure(ctx, collector, f"{folder} for {entity}")


@then(parsers.parse('the check "{path}" fails on "{target}"'))
def check_fails(ctx: dict[str, Any], collector: ReportCollector, path: str, target: str) -> None:
    sql.resolve(path)
    _expect_failure(ctx, collector, f"{path} on {target}")


@then(parsers.parse('the contract "{path}" fails'))
def contract_fails(ctx: dict[str, Any], collector: ReportCollector, path: str) -> None:
    sql.resolve(path)
    _expect_failure(ctx, collector, path)


@then(parsers.parse('every defect in "{folder}" is covered by "{feature}"'))
def every_defect_covered(folder: str, feature: str) -> None:
    text = (FEATURES / feature).read_text(encoding="utf-8")
    listed = set(re.findall(r"sql/defects/[\w/]+\.sql", text))
    missing = sorted(set(sql.files(folder)) - listed)
    assert not missing, f"no scenario applies: {missing}"

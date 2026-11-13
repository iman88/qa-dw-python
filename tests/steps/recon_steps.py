"""Reconciliation steps: compare source.sql with target.sql in a folder under sql/checks/recon/."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pytest_bdd import parsers, then, when

from clinical_dq.db.client import SqlClient
from clinical_dq.recon import checks as recon
from clinical_dq.reporting.collector import ReportCollector
from tests.support import attach

FEATURES = Path(__file__).parents[1] / "features"


def _reconcile(
    db: SqlClient, ctx: dict[str, Any], collector: ReportCollector, check: recon.ReconCheck
) -> None:
    result = recon.run_check(db, check)
    collector.add_recon(result)
    attach(f"reconcile {check.id}", result.to_dict())
    ctx["recon"] = result


@when(parsers.parse('I reconcile "{folder}" by key "{key}"'))
def reconcile(db: SqlClient, ctx: dict[str, Any], collector: ReportCollector, folder: str, key: str) -> None:
    _reconcile(db, ctx, collector, recon.make(folder, key))


@when(parsers.parse('I reconcile "{folder}" for entity "{entity}" by key "{key}"'))
def reconcile_entity(
    db: SqlClient, ctx: dict[str, Any], collector: ReportCollector, folder: str, entity: str, key: str
) -> None:
    _reconcile(db, ctx, collector, recon.make(folder, key, entity))


@then("source and target match")
def recon_matches(ctx: dict[str, Any]) -> None:
    result = ctx["recon"]
    assert result.source_count > 0, f"{result.name}: the source query returned nothing"
    assert result.passed, result.summary()


@then(parsers.parse('every reconciliation in "{folder}" is covered by "{feature}"'))
def every_recon_covered(folder: str, feature: str) -> None:
    text = (FEATURES / feature).read_text(encoding="utf-8")
    cells = set(re.findall(r"\|\s*([\w/.:-]+)\s*(?=\|)", text)) | set(re.findall(r'"([^"]+)"', text))
    missing = []
    for check in recon.CHECKS:
        if check.folder not in cells or (check.entity and check.entity not in cells):
            missing.append(check.id)
    assert not missing, f"not covered by any scenario: {missing}"


# ----------------------------------------------------------------------------- engines
@when(parsers.parse('I run every reconciliation with the "{engine}" engine'))
def run_all_with_engine(db: SqlClient, ctx: dict[str, Any], collector: ReportCollector, engine: str) -> None:
    results = recon.run_all(db, engine=engine)
    ctx.setdefault("engines", {})[engine] = results
    if engine == "pushdown":
        for r in results:
            collector.add_recon(r)


@then("every reconciliation passes")
def all_pass(ctx: dict[str, Any]) -> None:
    failed = [r.summary() for results in ctx["engines"].values() for r in results if not r.passed]
    assert not failed, failed


@then("no row was fetched from the database")
def nothing_fetched(ctx: dict[str, Any]) -> None:
    fetched = {r.name: r.stats["rows_fetched"] for r in ctx["engines"]["pushdown"] if r.stats["rows_fetched"]}
    assert not fetched, f"rows fetched: {fetched}"


@then("both engines give the same verdicts and row counts")
def engines_agree(ctx: dict[str, Any]) -> None:
    def summary(results: list) -> dict:
        return {r.name: (r.passed, r.source_count, r.target_count) for r in results}

    assert summary(ctx["engines"]["pushdown"]) == summary(ctx["engines"]["full"])


@when(parsers.parse('I reconcile "{folder}" on the copy with {buckets:d} push-down buckets'))
def reconcile_copy(
    db: SqlClient, ctx: dict[str, Any], mutation_layers: Any, folder: str, buckets: int
) -> None:
    check = next(c for c in recon.CHECKS if c.folder == folder and not c.entity)
    ctx["recon"] = recon.run_check(db, check, mutation_layers, engine="pushdown", buckets=buckets)


@then(parsers.parse("the reconciliation finds {n:d} mismatched values"))
def mismatches(ctx: dict[str, Any], n: int) -> None:
    assert len(ctx["recon"].mismatches) == n, ctx["recon"].summary()


@then(parsers.parse("at most {n:d} of the {buckets:d} buckets were fetched"))
def buckets_fetched(ctx: dict[str, Any], n: int, buckets: int) -> None:
    stats = ctx["recon"].stats
    assert stats["buckets"] == buckets and stats["buckets_differing"] <= n, stats
    assert stats["rows_fetched"] < stats["rows_total"] / 4, stats

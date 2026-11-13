"""Steps for 10_incremental_loads.feature: a second, incrementally built warehouse vs the full build."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from pytest_bdd import given, parsers, then, when

from clinical_dq import sql
from clinical_dq.config import Settings
from clinical_dq.data.entities import BY_NAME as ENTITY
from clinical_dq.db.client import SqlClient
from clinical_dq.etl import pipeline
from clinical_dq.etl.pipeline import BuildReport
from clinical_dq.layers import DEFAULT, Layers
from clinical_dq.recon import pushdown
from clinical_dq.reporting.collector import ReportCollector
from tests.steps.sql_steps import table_params
from tests.support import attach

INC = Layers(prefix="inc_")


def _day(text: str) -> datetime:
    value = datetime.fromisoformat(text)
    return value if value.tzinfo else value.replace(tzinfo=UTC)


@pytest.fixture(scope="session")
def incremental_build(db: SqlClient, settings: Settings, build: BuildReport) -> Iterator[Layers]:
    pipeline.run_incremental(
        db, INC, settings.data_seed, settings.subjects_per_study, pipeline.DEFAULT_CUTOFF
    )
    yield INC
    pipeline.drop(db, INC)


@given(parsers.parse('a second warehouse built incrementally from "{cutoff}", in schemas prefixed "inc_"'))
def second_warehouse(incremental_build: Layers, cutoff: str) -> None:
    assert _day(cutoff) == pipeline.DEFAULT_CUTOFF, f"the incremental build uses {pipeline.DEFAULT_CUTOFF}"


@when(parsers.parse('I run the query "{path}" on the incremental build with:'))
def run_on_incremental(
    db: SqlClient, ctx: dict[str, Any], incremental_build: Layers, path: str, datatable: list[list[str]]
) -> None:
    params = table_params(datatable)
    query = sql.sql(path, incremental_build)
    ctx.update(source=path, rows=db.query(query, sql.bind_params(query, params)))


def _compare(
    db: SqlClient,
    ctx: dict[str, Any],
    collector: ReportCollector,
    path: str,
    layer: str,
    key: str,
    identifiers: dict[str, str],
) -> None:
    full_query = sql.sql(path, DEFAULT, schema="{" + layer + "}", **identifiers)
    inc_query = sql.sql(path, INC, schema="{" + layer + "}", **identifiers)
    keys = tuple(k.strip() for k in key.split(","))
    label = f"{path} on {layer}" + (f" for {identifiers['entity']}" if "entity" in identifiers else "")
    result = pushdown.reconcile(db, f"full vs incremental: {label}", full_query, inc_query, keys)
    collector.add_recon(result)
    attach(label, result.to_dict())
    ctx["recon"] = result


@when(
    parsers.parse('I compare "{path}" on layer "{layer}" of both builds for entity "{entity}" by key "{key}"')
)
def compare_entity(
    db: SqlClient,
    ctx: dict[str, Any],
    collector: ReportCollector,
    incremental_build: Layers,
    path: str,
    layer: str,
    entity: str,
    key: str,
) -> None:
    _compare(db, ctx, collector, path, layer, key, pipeline.entity_params(ENTITY[entity]))


@when(parsers.parse('I compare "{path}" on layer "{layer}" of both builds by key "{key}"'))
def compare_plain(
    db: SqlClient,
    ctx: dict[str, Any],
    collector: ReportCollector,
    incremental_build: Layers,
    path: str,
    layer: str,
    key: str,
) -> None:
    _compare(db, ctx, collector, path, layer, key, {})


@then("both builds match")
def builds_match(ctx: dict[str, Any]) -> None:
    result = ctx["recon"]
    assert result.source_count > 0, f"{result.name}: nothing to compare"
    assert result.passed, result.summary()


def _checksums(db: SqlClient, layers: Layers) -> dict[str, tuple]:
    sums = {}
    for layer in ("hist", "latest", "dwh"):
        schema = getattr(layers, layer)
        for row in db.query(
            sql.load("sql/queries/incremental/tables_of_schema.sql"), {"schema_name": schema}
        ):
            query = sql.sql(
                "sql/checks/build_compare/table_checksum.sql", layers, schema=schema, table=row["table_name"]
            )
            result = db.query(query)[0]
            sums[f"{schema}.{row['table_name']}"] = (result["row_count"], result["checksum"])
    return sums


@when("I record a checksum of every table in the incremental build")
def record_checksums(db: SqlClient, ctx: dict[str, Any], incremental_build: Layers) -> None:
    ctx["before"] = _checksums(db, incremental_build)


@when(parsers.parse('the same batch from "{cutoff}" is applied again'))
def apply_again(db: SqlClient, incremental_build: Layers, cutoff: str) -> None:
    pipeline.apply_increment(db, incremental_build, _day(cutoff))


@then("every table of the incremental build has the same checksum as before")
def same_checksums(db: SqlClient, ctx: dict[str, Any], incremental_build: Layers) -> None:
    after = _checksums(db, incremental_build)
    changed = {t: (ctx["before"].get(t), v) for t, v in after.items() if ctx["before"].get(t) != v}
    assert len(after) >= 15 and not changed, f"changed by the re-run: {changed}"

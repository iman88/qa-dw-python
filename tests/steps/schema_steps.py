"""Schema contract steps: compare a layer with its reviewed contract file in sql/contracts/."""

from __future__ import annotations

import json
from typing import Any

from pytest_bdd import parsers, then, when

from clinical_dq import sql
from clinical_dq.db.client import SqlClient
from clinical_dq.dq import schema
from clinical_dq.reporting.collector import ReportCollector
from tests.support import attach


def _contract(path: str) -> dict[str, Any]:
    return json.loads(sql.resolve(path).read_text(encoding="utf-8"))["objects"]


@then(parsers.parse('the "{layer}" layer matches the contract "{path}"'))
def matches_contract(db: SqlClient, collector: ReportCollector, layer: str, path: str) -> None:
    assert path == schema.contract_id(layer), f"the {layer} contract lives at {schema.contract_id(layer)}"
    result = schema.check_layer(db, layer)
    collector.add_dq(result)
    attach(f"contract {path}", result.to_dict())
    assert result.passed, f"{result.failing_rows} differences with {path}: {result.sample}"


@then(parsers.parse('the contract "{path}" describes these objects:'))
def contract_objects(path: str, datatable: list[list[str]]) -> None:
    header, *rows = datatable
    objects = _contract(path)
    for row in rows:
        spec = dict(zip(header, row, strict=True))
        obj = objects.get(spec["object"])
        assert obj is not None, f"{spec['object']} is not in {path}"
        assert obj["type"] == spec["type"], spec
        assert obj.get("partition_key", "") == spec["partition key"], spec


@then(parsers.parse('the contract "{path}" declares these columns NOT NULL:'))
def contract_not_null(path: str, datatable: list[list[str]]) -> None:
    header, *rows = datatable
    objects = _contract(path)
    nullable = []
    for row in rows:
        spec = dict(zip(header, row, strict=True))
        columns = {c[0]: c for c in objects[spec["object"]]["columns"]}
        if not columns[spec["column"]][2]:
            nullable.append(f"{spec['object']}.{spec['column']}")
    assert not nullable, f"declared nullable in {path}: {nullable}"


@then(parsers.parse('the contract "{path}" is version "{version}", owned by "{owner}"'))
def contract_version(path: str, version: str, owner: str) -> None:
    body = json.loads(sql.resolve(path).read_text(encoding="utf-8"))
    assert (body["version"], body["owner"]) == (version, owner)


@then(parsers.parse('the contract "{path}" names these consumers:'))
def contract_consumers(path: str, datatable: list[list[str]]) -> None:
    body = json.loads(sql.resolve(path).read_text(encoding="utf-8"))
    assert body["consumers"] == [row[0] for row in datatable[1:]]


@when(parsers.parse('I apply the schema change "{path}" to the copy'))
def apply_schema_change(db: SqlClient, mutation_layers: Any, path: str) -> None:
    db.execute(sql.sql(path, mutation_layers))


@then(parsers.parse('the "{layer}" layer of the copy has no breaking change against "{path}"'))
def no_breaking_change(
    db: SqlClient, ctx: dict[str, Any], mutation_layers: Any, layer: str, path: str
) -> None:
    assert path == schema.contract_id(layer)
    contract = schema.load_contract(layer)
    ctx["diffs"] = schema.compare(contract["objects"], schema.actual_schema(db, layer, mutation_layers))
    ctx["contract_version"] = contract["version"]
    breaking = [d for d in ctx["diffs"] if d["severity"] == "breaking"]
    assert not breaking, breaking
    assert schema.check_layer(db, layer, mutation_layers).passed


@then("this compatible change is reported:")
def compatible_reported(ctx: dict[str, Any], datatable: list[list[str]]) -> None:
    header, row = datatable[0], datatable[1]
    expected = dict(zip(header, row, strict=True))
    found = [
        d
        for d in ctx["diffs"]
        if d["severity"] == "compatible"
        and d["object"] == expected["object"]
        and d.get("column") == expected["column"]
        and d["change"] == expected["change"]
    ]
    assert found, f"reported: {ctx['diffs']}"


@then(parsers.parse('the contract version would become "{version}"'))
def version_bump(ctx: dict[str, Any], version: str) -> None:
    assert schema.next_version(ctx["contract_version"], ctx["diffs"]) == version

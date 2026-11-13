"""Schema contracts: the agreed shape of each layer, checked against the database catalogue.

A contract (``sql/contracts/<layer>.json``) lists every table, partitioned table and view with
its columns in order (name, type, NOT NULL) and the partition keys. It is reviewed like code: a
change to the warehouse shape is a deliberate edit to the contract, never a surprise downstream.

``clinical-dq contract`` snapshots the current build into the contract files. Review the diff
before committing; the snapshot is only as right as the build it came from.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clinical_dq import sql
from clinical_dq.db.client import SqlClient
from clinical_dq.dq.checks import DqResult
from clinical_dq.layers import DEFAULT, Layers

CONTRACT_LAYERS = ("latest", "hist", "dwh")
COLUMNS_SQL = "sql/checks/schema/columns.sql"
PARTITION_KEYS_SQL = "sql/checks/schema/partition_keys.sql"


def contract_id(layer: str) -> str:
    return f"sql/contracts/{layer}.json"


def contract_path(layer: str) -> Path:
    return sql.SQL_ROOT / "contracts" / f"{layer}.json"


def actual_schema(db: SqlClient, layer: str, layers: Layers = DEFAULT) -> dict[str, Any]:
    schema = getattr(layers, layer)
    objects: dict[str, Any] = {}
    for row in db.query(sql.load(COLUMNS_SQL), {"schema_name": schema}):
        obj = objects.setdefault(row["object_name"], {"type": row["object_type"], "columns": []})
        obj["columns"].append([row["column_name"], row["data_type"], row["not_null"]])
    for row in db.query(sql.load(PARTITION_KEYS_SQL), {"schema_name": schema}):
        objects[row["object_name"]]["partition_key"] = row["partition_key"]
    return dict(sorted(objects.items()))


# Type changes that cannot break a consumer: every old value fits the new type unchanged.
WIDENINGS = {
    ("smallint", "integer"),
    ("smallint", "bigint"),
    ("integer", "bigint"),
    ("smallint", "numeric"),
    ("integer", "numeric"),
    ("bigint", "numeric"),
    ("character varying", "text"),
    ("character(1)", "text"),
    ("character(2)", "text"),
    ("real", "double precision"),
}
CONTRACT_DEFAULTS = {
    "latest": {
        "owner": "data engineering",
        "consumers": ["dwh build (sql/build/dimensions, sql/build/facts)"],
    },
    "hist": {"owner": "data engineering", "consumers": ["dwh build (dim_site, type 2)", "audit and replay"]},
    "dwh": {
        "owner": "data engineering",
        "consumers": [
            "safety reporting (v_safety_by_study_month)",
            "medical monitoring (v_adverse_event_detail)",
            "narrative service input (v_adverse_event_detail)",
        ],
    },
}


def load_contract(layer: str) -> dict[str, Any]:
    return json.loads(contract_path(layer).read_text(encoding="utf-8"))


def compare(expected: dict[str, Any], actual: dict[str, Any]) -> list[dict[str, Any]]:
    """Differences between contract and database. Each one is ``breaking`` or ``compatible``.

    Breaking: a consumer's query can fail or return wrong results (something it reads is gone,
    retyped, or may now be NULL; a partition key changed). Compatible: nothing a consumer reads
    changes (a new object, a new nullable column, a widened type, a NOT NULL added, a new order).
    """
    diffs: list[dict[str, Any]] = []

    def add(severity: str, obj: str, change: str, **detail: Any) -> None:
        diffs.append({"severity": severity, "object": obj, "change": change, **detail})

    for name in sorted(expected.keys() - actual.keys()):
        add("breaking", name, "object removed", expected=expected[name]["type"])
    for name in sorted(actual.keys() - expected.keys()):
        add("compatible", name, "new object", actual=actual[name]["type"])
    for name in sorted(expected.keys() & actual.keys()):
        exp, act = expected[name], actual[name]
        if exp["type"] != act["type"]:
            add("breaking", name, "object type changed", expected=exp["type"], actual=act["type"])
        if exp.get("partition_key") != act.get("partition_key"):
            add(
                "breaking",
                name,
                "partition key changed",
                expected=exp.get("partition_key"),
                actual=act.get("partition_key"),
            )
        exp_cols = {c[0]: c for c in exp["columns"]}
        act_cols = {c[0]: c for c in act["columns"]}
        for col in [c for c in exp_cols if c not in act_cols]:
            add("breaking", name, "column removed", column=col)
        for col in [c for c in act_cols if c not in exp_cols]:
            if act_cols[col][2]:
                add("breaking", name, "new NOT NULL column", column=col, actual=act_cols[col][1])
            else:
                add("compatible", name, "new nullable column", column=col, actual=act_cols[col][1])
        for col in [c for c in exp_cols if c in act_cols]:
            old_type, new_type = exp_cols[col][1], act_cols[col][1]
            if old_type != new_type:
                widened = (
                    old_type.split("(")[0] if old_type.startswith("character varying") else old_type,
                    new_type,
                )
                severity = "compatible" if widened in WIDENINGS else "breaking"
                add(
                    severity,
                    name,
                    "type widened" if severity == "compatible" else "type changed",
                    column=col,
                    expected=old_type,
                    actual=new_type,
                )
            if exp_cols[col][2] and not act_cols[col][2]:
                add("breaking", name, "NOT NULL dropped", column=col)
            if not exp_cols[col][2] and act_cols[col][2]:
                add("compatible", name, "NOT NULL added", column=col)
        if [c for c in exp_cols if c in act_cols] != [c for c in act_cols if c in exp_cols]:
            add("compatible", name, "column order changed")
    return diffs


def next_version(version: str, diffs: list[dict[str, Any]]) -> str:
    """Semantic versioning: breaking -> major, compatible -> minor, no change -> same."""
    major, minor, patch = (int(x) for x in version.split("."))
    if any(d["severity"] == "breaking" for d in diffs):
        return f"{major + 1}.0.0"
    if diffs:
        return f"{major}.{minor + 1}.0"
    return version


def write_contract(db: SqlClient, layer: str) -> tuple[Path, str, list[dict[str, Any]]]:
    """Snapshot the current build into the contract, bumping the version by what changed."""
    path = contract_path(layer)
    actual = actual_schema(db, layer)
    old = load_contract(layer) if path.exists() else {}
    diffs = compare(old.get("objects", {}), actual) if old else []
    version = next_version(old.get("version", "1.0.0"), diffs) if old else "1.0.0"
    defaults = CONTRACT_DEFAULTS.get(layer, {})
    body = {
        "layer": layer,
        "version": version,
        "owner": old.get("owner", defaults.get("owner", "")),
        "consumers": old.get("consumers", defaults.get("consumers", [])),
        "objects": actual,
    }
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return path, version, diffs


def check_layer(db: SqlClient, layer: str, layers: Layers = DEFAULT) -> DqResult:
    """Fails only on breaking changes; compatible ones are reported in the sample, with the version to bump to."""
    contract = load_contract(layer)
    diffs = compare(contract["objects"], actual_schema(db, layer, layers))
    breaking = [d for d in diffs if d["severity"] == "breaking"]
    version = contract.get("version", "1.0.0")
    return DqResult(
        name=contract_id(layer),
        layer=layer,
        description=f"The {layer} layer has no breaking change against contract v{version} "
        f"(compatible changes are reported; next version would be {next_version(version, diffs)})",
        failing_rows=len(breaking),
        sample=(breaking + [d for d in diffs if d["severity"] == "compatible"])[:20],
        sql=f"{COLUMNS_SQL} + {PARTITION_KEYS_SQL}",
    )


def run_all(db: SqlClient, layers: Layers = DEFAULT) -> list[DqResult]:
    return [check_layer(db, layer, layers) for layer in CONTRACT_LAYERS]

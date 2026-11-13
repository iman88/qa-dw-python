"""Generic SQL steps, usable from any feature.

Short SQL is written in the feature itself (docstring). Anything longer lives in a file under
``sql/`` and the feature names the path, so a reader always knows exactly what runs:

    When I run the query "sql/queries/warehouse/study_safety_source.sql" with:
      | study_id  |
      | STUDY-001 |
    Then the result is the same as the query "sql/queries/warehouse/study_safety_dwh.sql"

    When I run the check "sql/checks/rules/keys/referential_integrity.sql" with:
      | layer | fact               | fk         | dim         | pk         |
      | dwh   | fact_adverse_event | subject_sk | dim_subject | subject_sk |
    Then it finds no offending rows

Data table values fill both {identifier} placeholders and :bind parameters in the file.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pytest_bdd import given, parsers, then, when

from clinical_dq import sql
from clinical_dq.db.client import SqlClient
from clinical_dq.dq import checks as dq
from clinical_dq.dq.checks import partitions_scanned
from clinical_dq.etl.pipeline import BuildReport
from clinical_dq.reporting.collector import ReportCollector
from tests.support import attach


def table_params(datatable: list[list[str]] | None) -> dict[str, str]:
    """A two-row data table (header + values) as a dict."""
    if not datatable:
        return {}
    header, values = datatable[0], datatable[1]
    return dict(zip(header, values, strict=True))


def show(value: Any) -> str:
    """How a database value is written in a feature table."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal | float):
        return f"{float(value):g}"
    if isinstance(value, date | datetime):
        return value.isoformat()
    return str(value)


def run(db: SqlClient, ctx: dict[str, Any], text: str, params: dict[str, str], source: str) -> None:
    query = sql.render(text, **params)
    binds = sql.bind_params(query, params)
    ctx.update(query=query, params=binds, table=params, source=source, rows=db.query(query, binds))
    attach(f"query {source}", {"sql": query, "params": binds, "rows": ctx["rows"][:50]})


# ----------------------------------------------------------------------------- setup
@given("the clinical warehouse is built")
def warehouse_built(build: BuildReport) -> BuildReport:
    return build


# ----------------------------------------------------------------------------- queries
@when("I run the query:")
def run_inline(db: SqlClient, ctx: dict[str, Any], docstring: str) -> None:
    run(db, ctx, docstring, {}, "inline SQL")


@when(parsers.parse('I run the query "{path}"'))
def run_file(db: SqlClient, ctx: dict[str, Any], path: str) -> None:
    run(db, ctx, sql.load(path), {}, path)


@when(parsers.parse('I run the query "{path}" with:'))
def run_file_with(db: SqlClient, ctx: dict[str, Any], path: str, datatable: list[list[str]]) -> None:
    run(db, ctx, sql.load(path), table_params(datatable), path)


@when(parsers.parse('I write with "{statement}", read back with "{probe}" and roll back, with:'))
def write_and_roll_back(
    db: SqlClient, ctx: dict[str, Any], statement: str, probe: str, datatable: list[list[str]]
) -> None:
    params = table_params(datatable)
    write, read = sql.sql(statement, **params), sql.sql(probe, **params)
    ctx["rows"] = db.rollback_probe(write, read, sql.bind_params(write + read, params))


# ----------------------------------------------------------------------------- results
@then(parsers.parse("the result has {n:d} rows"))
def result_rows(ctx: dict[str, Any], n: int) -> None:
    assert len(ctx["rows"]) == n, f"{ctx['source']}: {len(ctx['rows'])} rows, expected {n}"


@then(parsers.parse("the result has at least {n:d} rows"))
def result_at_least_rows(ctx: dict[str, Any], n: int) -> None:
    assert len(ctx["rows"]) >= n, f"{ctx['source']}: {len(ctx['rows'])} rows, expected at least {n}"


@then("the result is empty")
def result_empty(ctx: dict[str, Any]) -> None:
    assert not ctx["rows"], f"{ctx['source']}: expected no rows, got {ctx['rows'][:5]}"


@then(parsers.parse("the result value is {n:d}"))
def result_value(ctx: dict[str, Any], n: int) -> None:
    value = next(iter(ctx["rows"][0].values()))
    assert value == n, f"{ctx['source']}: {value}, expected {n}"


@then(parsers.parse("the result value is at least {n:d}"))
def result_value_at_least(ctx: dict[str, Any], n: int) -> None:
    value = next(iter(ctx["rows"][0].values()))
    assert value >= n, f"{ctx['source']}: {value}, expected at least {n}"


@then("the result contains:")
def result_contains(ctx: dict[str, Any], datatable: list[list[str]]) -> None:
    header, *expected = datatable
    actual = [tuple(show(row.get(col)) for col in header) for row in ctx["rows"]]
    missing = [row for row in expected if tuple(row) not in actual]
    assert not missing, f"{ctx['source']}: rows not found {missing}; got {actual[:10]}"


@then(parsers.parse('the result is the same as the query "{path}"'))
def same_as_query(db: SqlClient, ctx: dict[str, Any], path: str) -> None:
    table = ctx["table"]  # the full data table: the second query may bind values the first did not
    other_sql = sql.render(sql.load(path), **table)
    other = db.query(other_sql, sql.bind_params(other_sql, table))

    def bag(rows: list[dict[str, Any]]) -> Counter:
        return Counter(tuple(sorted((k, show(v)) for k, v in r.items())) for r in rows)

    left, right = bag(ctx["rows"]), bag(other)
    assert ctx["rows"], f"{ctx['source']} returned nothing; the comparison would prove nothing"
    assert left == right, (
        f"{ctx['source']} vs {path}\n only in first: {list((left - right).elements())[:5]}"
        f"\n only in second: {list((right - left).elements())[:5]}"
    )


# ----------------------------------------------------------------------------- checks (rule files)
@when(parsers.parse('I run the check "{path}"'))
def run_check_plain(db: SqlClient, ctx: dict[str, Any], collector: ReportCollector, path: str) -> None:
    run_check_with(db, ctx, collector, path, [["layer"], ["dwh"]])


@when(parsers.parse('I run the check "{path}" with:'))
def run_check_with(
    db: SqlClient, ctx: dict[str, Any], collector: ReportCollector, path: str, datatable: list[list[str]]
) -> None:
    params = table_params(datatable)
    layer = params.pop("layer", "dwh")
    result = dq.run_check(db, dq.DqCheck(path, layer, params))
    collector.add_dq(result)
    attach(f"check {result.name}", result.to_dict())
    ctx["check"] = result


@then("it finds no offending rows")
def no_offending_rows(ctx: dict[str, Any]) -> None:
    r = ctx["check"]
    assert r.passed, f"{r.name}: {r.failing_rows} offending rows, e.g. {r.sample[:3]}\nSQL: {r.sql}"


# ----------------------------------------------------------------------------- partition pruning
@then("the planner reads only the partitions:")
def planner_reads(db: SqlClient, ctx: dict[str, Any], datatable: list[list[str]]) -> None:
    expected = sorted(row[0] for row in datatable[1:])
    scanned = partitions_scanned(db, ctx["query"], ctx["params"])
    assert scanned == expected, f"planner reads {scanned}"


@then(parsers.parse('the planner reads all {n:d} partitions of "{table}"'))
def planner_reads_all(db: SqlClient, ctx: dict[str, Any], n: int, table: str) -> None:
    scanned = [p for p in partitions_scanned(db, ctx["query"], ctx["params"]) if p.startswith(table)]
    assert len(scanned) == n, f"planner reads {len(scanned)} partitions of {table}: {scanned}"


@then("every check in the catalogue finds no offending rows")
def whole_catalogue(db: SqlClient, collector: ReportCollector) -> None:
    results = dq.run_all(db)
    for r in results:
        collector.add_dq(r)
    failed = [f"{r.name}: {r.failing_rows} offending rows" for r in results if not r.passed]
    assert not failed, "; ".join(failed)

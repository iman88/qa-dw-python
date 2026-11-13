"""Steps for hand-built change feeds (11_change_feed_edge_cases.feature), run in a small sandbox."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from pytest_bdd import given, parsers, then, when

from clinical_dq.db.client import SqlClient
from clinical_dq.dq import checks as dq
from clinical_dq.etl.sandbox import Sandbox
from clinical_dq.layers import Layers

OPEN = datetime(9999, 12, 31, tzinfo=UTC)


def ts(text: str) -> datetime:
    """'2025-03-01 10:00' (UTC) or '2026-03-29 02:59+02:00' (with an offset)."""
    value = datetime.fromisoformat(text.strip())
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def show_ts(value: datetime) -> str:
    return "open" if value >= OPEN else value.astimezone(UTC).strftime("%Y-%m-%d %H:%M")


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


@pytest.fixture
def sandbox(db: SqlClient) -> Iterator[Sandbox]:
    box = Sandbox(db, Layers(prefix="fx_"))
    yield box
    box.drop()


@given("an empty change feed for visits")
def empty_feed(sandbox: Sandbox, ctx: dict[str, Any]) -> None:
    sandbox.reset()
    ctx["events"] = []


@given("these visit events arrive:")
def events_arrive(ctx: dict[str, Any], datatable: list[list[str]]) -> None:
    header, *rows = datatable
    for row in rows:
        r = dict(zip(header, row, strict=True))
        ctx["events"].append(
            {
                "change_seq": int(r["change"]),
                "op": r["op"],
                "changed_at": ts(r["changed at"]),
                "ingested_at": ts(r["ingested at"]),
                "visit_id": r["visit"],
                "status": r["status"],
            }
        )


@when("history and latest are built in one go")
def build_in_one_go(sandbox: Sandbox, ctx: dict[str, Any]) -> None:
    sandbox.land(ctx["events"])
    sandbox.build()


@when(parsers.parse('history and latest are built incrementally from "{cutoff}"'))
def build_incrementally(sandbox: Sandbox, ctx: dict[str, Any], cutoff: str) -> None:
    start = ts(cutoff)
    first = [e for e in ctx["events"] if e["ingested_at"] < start]
    rest = [e for e in ctx["events"] if e["ingested_at"] >= start]
    assert first and rest, "pick a cutoff that splits the events into two batches"
    sandbox.land(first)
    sandbox.build()
    sandbox.land(rest)
    sandbox.increment(start)


@then("history holds:")
def history_holds(sandbox: Sandbox, datatable: list[list[str]]) -> None:
    header, *expected = datatable
    actual = []
    for h in sandbox.history():
        row = {
            "visit": h["visit_id"],
            "change": str(h["change_seq"]),
            "status": h["status"],
            "valid from": show_ts(h["valid_from"]),
            "valid to": show_ts(h["valid_to"]),
            "current": yes_no(h["is_current"]),
            "deleted": yes_no(h["is_deleted"]),
        }
        actual.append([row[c] for c in header])
    assert actual == expected, f"history is\n{actual}"


@then("latest holds:")
def latest_holds(sandbox: Sandbox, datatable: list[list[str]]) -> None:
    header, *expected = datatable
    actual = [[{"visit": r["visit_id"], "status": r["status"]}[c] for c in header] for r in sandbox.latest()]
    assert actual == expected, f"latest is {actual}"


@then("latest holds no visits")
def latest_empty(sandbox: Sandbox) -> None:
    assert sandbox.latest() == []


@then(parsers.parse('the version of {visit} valid at "{moment}" is change {change:d}'))
def version_valid_at(sandbox: Sandbox, visit: str, moment: str, change: int) -> None:
    at = ts(moment)
    valid = [
        h["change_seq"]
        for h in sandbox.history()
        if h["visit_id"] == visit and h["valid_from"] <= at < h["valid_to"]
    ]
    assert valid == [change], f"valid at {moment}: {valid}"


@then("the history timeline rules find no offending rows")
def timeline_rules(db: SqlClient, sandbox: Sandbox) -> None:
    for rule in ("scd2_no_overlap", "scd2_single_current"):
        chk = dq.DqCheck(dq.RULE_FILES[rule], "hist", {"table": "visit_history", "key": "visit_id"})
        result = dq.run_check(db, chk, sandbox.layers)
        assert result.passed, f"{result.name}: {result.sample}"

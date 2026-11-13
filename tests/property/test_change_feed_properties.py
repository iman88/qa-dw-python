"""Property-based tests: random change feeds through the real history and latest SQL.

Hypothesis generates feeds nobody would think to write by hand: interleaved keys, several changes
at the same instant, events arriving days late and out of order, redelivered duplicates, deletes
and re-inserts. For every generated feed the invariants below must hold. When one fails,
Hypothesis shrinks the feed to the smallest one that still fails and prints it.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from clinical_dq.db.client import SqlClient
from clinical_dq.dq import checks as dq
from clinical_dq.etl.sandbox import Sandbox
from clinical_dq.layers import Layers

pytestmark = pytest.mark.property

BASE = datetime(2025, 3, 1, tzinfo=UTC)
STATUSES = ["SCHEDULED", "COMPLETED", "MISSED"]


@st.composite
def change_feeds(draw: st.DrawFn) -> list[dict]:
    keys = [f"V{i}" for i in range(1, draw(st.integers(1, 3)) + 1)]
    # Per key: an insert, then updates, deletes and re-inserts.
    plans = {}
    for key in keys:
        ops, alive = ["I"], True
        for _ in range(draw(st.integers(0, 4))):
            op = draw(st.sampled_from(["U", "U", "D"])) if alive else "I"
            alive = op != "D"
            ops.append(op)
        plans[key] = ops
    # Interleave the keys into one source log; the log order is the change number.
    order = [k for k in keys for _ in plans[k]]
    order = draw(st.permutations(order))
    position = dict.fromkeys(keys, 0)
    clock, events = BASE, []
    for seq, key in enumerate(order, start=1):
        op = plans[key][position[key]]
        position[key] += 1
        clock += timedelta(minutes=draw(st.sampled_from([0, 0, 1, 30, 600])))  # 0 = same instant
        delay = timedelta(minutes=draw(st.sampled_from([1, 5, 90, 1440, 4320])))  # up to 3 days late
        event = {
            "change_seq": seq,
            "op": op,
            "changed_at": clock,
            "ingested_at": clock + delay,
            "visit_id": key,
            "status": draw(st.sampled_from(STATUSES)),
        }
        events.append(event)
        if draw(st.integers(0, 9)) == 0:  # redelivered by a retried batch
            events.append(
                {**event, "ingested_at": event["ingested_at"] + timedelta(hours=draw(st.integers(1, 30)))}
            )
    return events


def expected_latest(events: list[dict]) -> list[dict]:
    """The reference model: per key, the change with the highest change number, unless it is a delete."""
    last: dict[str, dict] = {}
    for e in sorted(events, key=lambda e: e["change_seq"]):
        last[e["visit_id"]] = e
    return [
        {"visit_id": k, "status": e["status"], "last_change_seq": e["change_seq"]}
        for k, e in sorted(last.items())
        if e["op"] != "D"
    ]


@pytest.fixture(scope="module")
def boxes(db: SqlClient) -> Iterator[tuple[Sandbox, Sandbox]]:
    full, incremental = Sandbox(db, Layers(prefix="pf_")), Sandbox(db, Layers(prefix="pi_"))
    yield full, incremental
    full.drop()
    incremental.drop()


PROFILE = settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)


@PROFILE
@given(feed=change_feeds())
def test_latest_is_the_highest_change_per_key_and_deletes_drop_out(boxes, feed) -> None:
    full, _ = boxes
    full.reset()
    full.land(feed)
    full.build()
    assert full.latest() == expected_latest(feed)


@PROFILE
@given(feed=change_feeds())
def test_history_keeps_every_change_once_on_a_clean_timeline(db, boxes, feed) -> None:
    full, _ = boxes
    full.reset()
    full.land(feed)
    full.build()
    history = full.history()
    assert sorted(h["change_seq"] for h in history) == sorted({e["change_seq"] for e in feed})
    for rule in ("scd2_no_overlap", "scd2_single_current"):
        check = dq.DqCheck(dq.RULE_FILES[rule], "hist", {"table": "visit_history", "key": "visit_id"})
        result = dq.run_check(db, check, full.layers)
        assert result.passed, f"{rule}: {result.sample}"


@PROFILE
@given(feed=change_feeds(), split=st.floats(0.1, 0.9))
def test_incremental_load_equals_full_load(boxes, feed, split) -> None:
    full, incremental = boxes
    arrivals = sorted({e["ingested_at"] for e in feed})
    cutoff = arrivals[min(int(len(arrivals) * split), len(arrivals) - 1)]

    full.reset()
    full.land(feed)
    full.build()

    incremental.reset()
    incremental.land([e for e in feed if e["ingested_at"] < cutoff])
    incremental.build()
    incremental.land([e for e in feed if e["ingested_at"] >= cutoff])
    incremental.increment(cutoff)

    assert incremental.history() == full.history()
    assert incremental.latest() == full.latest()

    incremental.increment(cutoff)  # applying the same batch again changes nothing (idempotent)
    assert incremental.history() == full.history()
    assert incremental.latest() == full.latest()

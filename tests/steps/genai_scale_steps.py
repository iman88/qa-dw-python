"""Steps for 15_genai_at_scale.feature: evaluation set, stored runs, regression statistics, judge calibration."""

from __future__ import annotations

from typing import Any

import pytest
from pytest_bdd import given, parsers, then, when

from clinical_dq.db.client import SqlClient
from clinical_dq.genai import evalset, runner
from clinical_dq.genai.judge import ClaudeJudge, ReferenceJudge
from clinical_dq.genai.stats import cohen_kappa, regression_test
from clinical_dq.genai.summariser import TemplateSummariser
from tests.support import HallucinatingSummariser

LABELLED_EVENTS = [
    {"ae_id": "AE-1", "meddra_pt": "Neutropenia", "grade": 4, "is_serious": True},
    {"ae_id": "AE-2", "meddra_pt": "Nausea", "grade": 2, "is_serious": False},
]


@when(parsers.parse('the evaluation set is built from "{path}"'))
def build_set(db: SqlClient, ctx: dict[str, Any], path: str) -> None:
    assert path == evalset.QUERY
    ctx["evalset"] = evalset.build(db)


@then("the evaluation set holds these cases:")
def set_contents(ctx: dict[str, Any], datatable: list[list[str]]) -> None:
    header, *rows = datatable
    expected = {r[header.index("kind")]: int(r[header.index("cases")]) for r in rows}
    assert {kind: ctx["evalset"].count(kind) for kind in expected} == expected
    assert len(ctx["evalset"].cases) == sum(expected.values())


@then("building it again gives the same version")
def stable_version(db: SqlClient, ctx: dict[str, Any]) -> None:
    assert evalset.build(db).version == ctx["evalset"].version and len(ctx["evalset"].version) == 12


def _run(db: SqlClient, ctx: dict[str, Any], engine: Any) -> None:
    ctx.setdefault("runs", []).append(runner.run(db, engine, ctx["evalset"]))


@when(parsers.parse('the "{engine}" engine summarises every case'))
@when(parsers.parse('the "{engine}" engine summarises every case again'))
def engine_runs(db: SqlClient, ctx: dict[str, Any], engine: str) -> None:
    assert engine == "template", "live engines run through `clinical-dq eval` (they cost money)"
    _run(db, ctx, TemplateSummariser())


@when("a model that invents events summarises every case")
def inventing_model(db: SqlClient, ctx: dict[str, Any]) -> None:
    ctx.setdefault("runs", []).append(runner.run(db, HallucinatingSummariser(), ctx["evalset"], store=False))


@then("every metric passes on every case")
def all_metrics(ctx: dict[str, Any]) -> None:
    run = ctx["runs"][-1]
    assert all(p == t for p, t in run.metrics.values()), (run.metrics, run.failures[:3])


@then(
    parsers.parse(
        "the 95th percentile latency is under {ms:d} ms and the cost per narrative is under {usd:f} USD"
    )
)
def budgets(ctx: dict[str, Any], ms: int, usd: float) -> None:
    run = ctx["runs"][-1]
    assert run.p95_latency_ms < ms and run.cost_per_narrative < usd, (
        run.p95_latency_ms,
        run.cost_per_narrative,
    )


@then("the run is stored with its engine, model, prompt version and evaluation set version")
def stored(db: SqlClient, ctx: dict[str, Any]) -> None:
    run = ctx["runs"][-1]
    rows = db.query(
        "SELECT engine, model, prompt_version, evalset_version, metric FROM qa_monitor.genai_eval_runs "
        "WHERE run_id = :r",
        {"r": run.run_id},
    )
    assert len(rows) == len(run.metrics)
    assert {(r["engine"], r["model"], r["prompt_version"], r["evalset_version"]) for r in rows} == {
        ("template", "none", "template-v1", run.evalset_version)
    }


@then("the second run was compared with the first on every metric")
def compared(ctx: dict[str, Any]) -> None:
    assert set(ctx["runs"][-1].comparisons) == set(ctx["runs"][-1].metrics)


@then("no metric has regressed")
def no_regression(ctx: dict[str, Any]) -> None:
    assert ctx["runs"][-1].regressions == []


@then("these metrics pass on no case:")
def metrics_never_pass(ctx: dict[str, Any], datatable: list[list[str]]) -> None:
    metrics = ctx["runs"][-1].metrics
    assert {m: metrics[m][0] for m in (r[0] for r in datatable[1:])} == {r[0]: 0 for r in datatable[1:]}


@then("these metrics still pass on every case:")
def metrics_always_pass(ctx: dict[str, Any], datatable: list[list[str]]) -> None:
    metrics = ctx["runs"][-1].metrics
    assert all(metrics[r[0]][0] == metrics[r[0]][1] for r in datatable[1:])


@when(parsers.parse("a metric passed {before:d} of {cases:d} cases before and {after:d} of {cases2:d} now"))
def drop(ctx: dict[str, Any], before: int, cases: int, after: int, cases2: int) -> None:
    ctx["comparison"] = regression_test(before, cases, after, cases2)


@then(parsers.parse("the drop is {verdict}"))
def drop_verdict(ctx: dict[str, Any], verdict: str) -> None:
    expected = verdict == "a regression"
    assert ctx["comparison"].regression is expected, ctx["comparison"]


@given("these narratives were labelled by people:", target_fixture="labelled")
def labelled(datatable: list[list[str]]) -> list[tuple[str, bool]]:
    return [(row[0], row[1] == "yes") for row in datatable[1:]]


@when(parsers.parse('the "{name}" judge judges every labelled narrative'))
def judge_all(ctx: dict[str, Any], labelled: list[tuple[str, bool]], name: str) -> None:
    if name == "claude":
        try:
            judge: Any = ClaudeJudge()
        except Exception as exc:  # no credentials or SDK
            pytest.skip(f"Claude judge not configured: {exc}")
    else:
        judge = ReferenceJudge()
    ctx["human"] = [label for _, label in labelled]
    ctx["judge"] = [judge.judge(LABELLED_EVENTS, text).acceptable for text, _ in labelled]


@then(parsers.parse("the judge agrees with the people on {n:d} of {total:d} narratives"))
def agreement(ctx: dict[str, Any], n: int, total: int) -> None:
    agree = sum(h == j for h, j in zip(ctx["human"], ctx["judge"], strict=True))
    assert (agree, len(ctx["human"])) == (n, total), list(zip(ctx["human"], ctx["judge"], strict=True))


@then(parsers.parse("Cohen's kappa is {kappa:f}, so the judge can be trusted"))
def kappa_exact(ctx: dict[str, Any], kappa: float) -> None:
    assert cohen_kappa(ctx["human"], ctx["judge"]) == kappa >= 0.6


@then(parsers.parse("Cohen's kappa is at least {kappa:f}, so the judge can be trusted"))
def kappa_at_least(ctx: dict[str, Any], kappa: float) -> None:
    assert cohen_kappa(ctx["human"], ctx["judge"]) >= kappa

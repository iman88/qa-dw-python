"""Run the evaluation set through an engine, score it, store it, and compare with the previous run.

Every run is stored in qa_monitor.genai_eval_runs with the engine, model, prompt version and
evaluation-set version, so a score is only ever compared with a score on the same set. A drop is
called a regression only when it is statistically significant (stats.regression_test). Each run is
also held to budgets: 95th-percentile latency and cost per narrative.

    clinical-dq eval
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from clinical_dq import sql
from clinical_dq.db.client import SqlClient
from clinical_dq.genai.evalset import EvalSet
from clinical_dq.genai.evaluator import evaluate
from clinical_dq.genai.stats import Comparison, percentile, regression_test
from clinical_dq.genai.summariser import SYSTEM_PROMPT, Summariser

TABLE = "sql/results/genai_eval_table.sql"
PREVIOUS = "sql/queries/genai/previous_eval_run.sql"
# USD per million tokens (input, output); from the Claude API price list.
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.1, 0.5)}


@dataclass
class EvalRun:
    run_id: str
    engine: str
    model: str
    prompt_version: str
    evalset_version: str
    metrics: dict[str, list[int]] = field(default_factory=dict)  # metric -> [passed, total]
    latencies_ms: list[float] = field(default_factory=list)
    cost_usd: float = 0.0
    failures: list[dict[str, Any]] = field(default_factory=list)
    comparisons: dict[str, Comparison] = field(default_factory=dict)

    @property
    def p95_latency_ms(self) -> float:
        return round(percentile(self.latencies_ms, 95), 1)

    @property
    def cost_per_narrative(self) -> float:
        return self.cost_usd / max(len(self.latencies_ms), 1)

    @property
    def regressions(self) -> list[str]:
        return [m for m, c in self.comparisons.items() if c.regression]


def engine_identity(engine: Summariser) -> tuple[str, str]:
    """(model, prompt version) of an engine, so runs with different prompts are never mixed up."""
    inner = getattr(engine, "primary", engine)
    model = getattr(inner, "model", "none")
    if model == "none":
        return model, f"{engine.name}-v1"
    return model, hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:12]


def _cost(engine: Summariser, model: str) -> float:
    usage = getattr(getattr(engine, "primary", engine), "last_usage", {}) or {}
    price_in, price_out = PRICES.get(model, (0.0, 0.0))
    return (usage.get("input_tokens", 0) * price_in + usage.get("output_tokens", 0) * price_out) / 1_000_000


def run(db: SqlClient, engine: Summariser, evalset: EvalSet, store: bool = True) -> EvalRun:
    model, prompt_version = engine_identity(engine)
    result = EvalRun(
        f"eval-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}",
        engine.name,
        model,
        prompt_version,
        evalset.version,
    )
    for case in evalset.cases:
        started = time.perf_counter()
        out = engine.summarise(case.subject_id, case.events)
        result.latencies_ms.append((time.perf_counter() - started) * 1000)
        result.cost_usd += _cost(engine, model)
        verdict = evaluate(case.case_id, engine.name, case.subject_id, case.events, out)
        for metric, ok in verdict.metrics.items():
            passed_total = result.metrics.setdefault(metric, [0, 0])
            passed_total[0] += int(ok)
            passed_total[1] += 1
        if not verdict.passed:
            result.failures.append({"case": case.case_id, "kind": case.kind, "reasons": verdict.reasons})
    if store:
        _store_and_compare(db, result)
    return result


def _store_and_compare(db: SqlClient, result: EvalRun) -> None:
    db.execute_script(sql.load(TABLE))
    previous = db.query(
        sql.load(PREVIOUS),
        {"evalset_version": result.evalset_version, "engine": result.engine, "run_id": result.run_id},
    )
    for row in previous:
        if row["metric"] in result.metrics:
            passed, total = result.metrics[row["metric"]]
            result.comparisons[row["metric"]] = regression_test(row["passed"], row["total"], passed, total)
    ran_at = datetime.now(UTC)
    db.insert_many(
        "qa_monitor.genai_eval_runs",
        [
            {
                "run_id": result.run_id,
                "ran_at": ran_at,
                "engine": result.engine,
                "model": result.model,
                "prompt_version": result.prompt_version,
                "evalset_version": result.evalset_version,
                "metric": metric,
                "passed": passed,
                "total": total,
                "p95_latency_ms": result.p95_latency_ms,
                "cost_usd": result.cost_usd,
            }
            for metric, (passed, total) in result.metrics.items()
        ],
    )

"""Command line. Everything works without any AI: Claude is optional and only used by `serve`
when GENAI_PROVIDER=claude, with automatic fallback to the template.

    clinical-dq build             generate data and build src, raw, hist, latest, dwh
    clinical-dq check             run every reconciliation, rule and schema contract; write the report
    clinical-dq defects           list the bugs that can be injected
    clinical-dq inject <defect>   break the main build on purpose (`build` again to undo)
    clinical-dq contract          snapshot the current schema of each layer into sql/contracts/
    clinical-dq monitor           every check plus freshness, volume and drift; results stored, alert on failure
    clinical-dq affected          the pytest command for the tests a change can affect
    clinical-dq evidence          freeze the last run's reports with SHA-256 hashes (audit evidence)
    clinical-dq eval              GenAI evaluation set: scores stored, real regressions flagged
    clinical-dq bigquery          the BigQuery version of the build, and SQL coverage for BigQuery
    clinical-dq serve             start the narrative service on http://127.0.0.1:8000 (/docs)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import UTC, datetime

from clinical_dq.config import get_settings
from clinical_dq.db.client import SqlClient
from clinical_dq.dq import checks as dq
from clinical_dq.dq import schema
from clinical_dq.etl import defects, pipeline
from clinical_dq.layers import DEFAULT
from clinical_dq.recon import checks as recon
from clinical_dq.reporting.collector import ReportCollector


def _db() -> SqlClient:
    db = SqlClient(get_settings().db_url)
    db.wait_until_ready()
    return db


def cmd_build() -> int:
    settings = get_settings()
    report = pipeline.run(_db(), DEFAULT, settings.data_seed, settings.subjects_per_study)
    for k, v in report.stats.items():
        print(f"  {k:28} {v}")
    print(f"  scripts run: {len(report.scripts)} from sql/build/")
    return 0


def cmd_check() -> int:
    db, collector, failures = _db(), ReportCollector(), 0
    for r in recon.run_all(db):
        collector.add_recon(r)
        failures += not r.passed
        print(("PASS " if r.passed else "FAIL ") + r.summary())
    for d in dq.run_all(db) + schema.run_all(db):
        collector.add_dq(d)
        failures += not d.passed
        print(("PASS " if d.passed else "FAIL ") + f"{d.name} ({d.failing_rows} offending rows)")
        if not d.passed:
            for row in d.sample[:3]:
                print(f"       {row}")
    path = collector.write(get_settings().reports_dir)
    print(f"\n{failures} failing checks. Report: {path}")
    return 1 if failures else 0


def cmd_defects() -> int:
    for d in sorted(defects.DEFECTS.values(), key=lambda d: d.path):
        print(f"  {d.name:32} {d.path}")
        print(f"  {'':32} {d.story}")
    return 0


def cmd_inject(name: str) -> int:
    rows = defects.inject(_db(), DEFAULT, name)
    affected = "schema changed" if rows < 0 else f"{rows} rows"
    print(
        f"Injected {name} ({affected}). Run 'clinical-dq check' to see it caught, 'clinical-dq build' to restore."
    )
    return 0


def cmd_contract() -> int:
    db = _db()
    for layer in schema.CONTRACT_LAYERS:
        path, version, diffs = schema.write_contract(db, layer)
        breaking = sum(d["severity"] == "breaking" for d in diffs)
        print(f"  {path}  v{version}  ({len(diffs)} changes, {breaking} breaking)")
        for d in diffs:
            print(f"      {d['severity']:10} {d['object']}.{d.get('column', '')} {d['change']}")
    print("Review the diff before committing: the contract is only as right as the build it came from.")
    return 0


def cmd_monitor(as_of: str | None, webhook: str | None) -> int:
    from clinical_dq import monitor
    from clinical_dq.data.generator import AS_OF

    moment = datetime.fromisoformat(as_of) if as_of else AS_OF
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    result = monitor.run(_db(), moment, webhook=webhook or os.getenv("ALERT_WEBHOOK_URL"))
    for f in result.failures:
        print(f"FAIL {f.check_id} ({f.offending_rows})")
    alert = "sent" if result.alert_sent else "not sent"
    print(f"{result.run_id}: {len(result.outcomes)} checks, {len(result.failures)} failing, alert {alert}.")
    print("Results stored in qa_monitor.check_results.")
    return 1 if result.failures else 0


def cmd_affected(since: str, files: list[str]) -> int:
    from clinical_dq import affected

    changed = files or affected.changed_since(since)
    print(f"# {len(changed)} changed files")
    print(affected.pytest_command(affected.affected_markers(changed)))
    return 0


def cmd_evidence() -> int:
    from clinical_dq import evidence, traceability

    reports = get_settings().reports_dir
    if (reports / "cucumber.json").exists():
        traceability.write_matrix(traceability.build_matrix(reports / "cucumber.json"), reports)
    pack = evidence.create_pack(reports, reports / "evidence", str(_db().scalar("SHOW server_version")))
    print(f"Evidence pack: {pack}")
    problems = evidence.verify_pack(pack)
    print("Verified: every file matches its SHA-256 hash." if not problems else "\n".join(problems))
    return 1 if problems else 0


def cmd_eval() -> int:
    from clinical_dq.genai import evalset, runner
    from clinical_dq.genai.summariser import get_summariser

    settings = get_settings()
    db = _db()
    engine = get_summariser(settings.genai_provider, settings.claude_model, settings.genai_fallback)
    cases = evalset.build(db)
    result = runner.run(db, engine, cases)
    print(
        f"{result.run_id}: engine {result.engine}, model {result.model}, prompt {result.prompt_version}, "
        f"set {result.evalset_version} ({len(cases.cases)} cases)"
    )
    for metric, (passed, total) in result.metrics.items():
        comparison = result.comparisons.get(metric)
        trend = f"  vs previous {comparison.before:.1%} (p={comparison.p_value})" if comparison else ""
        flag = "  REGRESSION" if comparison and comparison.regression else ""
        print(f"  {metric:20} {passed}/{total}{trend}{flag}")
    print(f"  p95 latency {result.p95_latency_ms} ms, cost {result.cost_usd:.4f} USD")
    return 1 if result.regressions or result.failures else 0


def cmd_bigquery(out: str) -> int:
    from pathlib import Path, PurePosixPath

    from clinical_dq import dialects
    from clinical_dq.data.entities import ENTITIES
    from clinical_dq.etl.pipeline import build_scripts, entity_params

    report = dialects.check_coverage()
    target = Path(out)
    target.mkdir(parents=True, exist_ok=True)
    written = 0
    for path in build_scripts():
        if dialects.classify(path)[0] == "not needed":
            continue
        entities = ENTITIES if PurePosixPath(path).stem.endswith("_entity") else [None]
        parts = [dialects.bigquery_sql(path, DEFAULT, **(entity_params(e) if e else {})) for e in entities]
        (target / PurePosixPath(path).name).write_text(";\n\n".join(parts) + ";\n", encoding="utf-8")
        written += 1
    print(f"{written} BigQuery build scripts written to {target}")
    print(
        f"coverage: {len(report['counterpart'])} hand-written, {len(report['portable'])} translated, "
        f"{len(report['not needed'])} not needed, {len(report['missing'])} missing"
    )
    return 1 if report["missing"] else 0


def cmd_serve(port: int) -> int:
    import uvicorn

    from clinical_dq.genai.service import create_app
    from clinical_dq.genai.summariser import get_summariser

    settings = get_settings()
    summariser = get_summariser(settings.genai_provider, settings.claude_model, settings.genai_fallback)
    print(f"Narrative engine: {summariser.name}. API docs: http://127.0.0.1:{port}/docs")
    uvicorn.run(create_app(summariser), host="127.0.0.1", port=port)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="clinical-dq", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build", help="generate data and build every layer")
    sub.add_parser("check", help="run all checks and write reports/data-quality-report.html")
    sub.add_parser("defects", help="list injectable defects")
    inject = sub.add_parser("inject", help="inject one defect into the main build")
    inject.add_argument("defect", choices=sorted(defects.DEFECTS))
    sub.add_parser("contract", help="snapshot the schema contracts from the current build")
    mon = sub.add_parser("monitor", help="every check plus freshness, volume and drift; store results, alert")
    mon.add_argument(
        "--as-of", help="the moment to judge freshness from (default: end of the synthetic data)"
    )
    mon.add_argument("--webhook", help="alert URL (default: ALERT_WEBHOOK_URL)")
    aff = sub.add_parser("affected", help="print the pytest command for the tests a change can affect")
    aff.add_argument("--since", default="origin/main", help="git ref to compare with (default: origin/main)")
    aff.add_argument("files", nargs="*", help="changed files (default: from git)")
    sub.add_parser("evidence", help="freeze the last run's reports with SHA-256 hashes (audit evidence)")
    sub.add_parser("eval", help="run the GenAI evaluation set, store the scores, flag real regressions")
    bq = sub.add_parser("bigquery", help="write the BigQuery version of the build and report SQL coverage")
    bq.add_argument("--out", default="reports/bigquery", help="folder for the BigQuery build scripts")
    serve = sub.add_parser("serve", help="start the narrative service")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    match args.command:
        case "build":
            return cmd_build()
        case "check":
            return cmd_check()
        case "defects":
            return cmd_defects()
        case "inject":
            return cmd_inject(args.defect)
        case "contract":
            return cmd_contract()
        case "monitor":
            return cmd_monitor(args.as_of, args.webhook)
        case "affected":
            return cmd_affected(args.since, args.files)
        case "evidence":
            return cmd_evidence()
        case "eval":
            return cmd_eval()
        case "bigquery":
            return cmd_bigquery(args.out)
        case "serve":
            return cmd_serve(args.port)
    return 2


if __name__ == "__main__":
    sys.exit(main())

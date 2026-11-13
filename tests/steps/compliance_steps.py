"""Steps for 14_compliance.feature: access control, traceability and evidence packs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pytest_bdd import given, parsers, then, when

from clinical_dq import evidence, traceability
from clinical_dq.config import ROOT
from clinical_dq.db.client import SqlClient


@then(parsers.parse('the role "{role}" is allowed or denied these queries:'))
def role_access(db: SqlClient, role: str, datatable: list[list[str]]) -> None:
    header, *rows = datatable
    wrong = []
    for row in rows:
        spec = dict(zip(header, row, strict=True))
        expected = spec["allowed"] == "yes"
        if db.allowed_as_role(role, spec["query"]) != expected:
            wrong.append(f"{spec['query']}: expected {'allowed' if expected else 'denied'}")
    assert not wrong, wrong


@then(parsers.parse('every requirement in "{path}" is tagged on at least one feature'))
def requirements_covered(path: str) -> None:
    ids = {r["id"] for r in traceability.load_requirements(ROOT / path)}
    tagged = {req for reqs in traceability.feature_requirements().values() for req in reqs}
    assert not ids - tagged, f"requirements without a feature: {sorted(ids - tagged)}"


@then(parsers.parse('every feature carries at least one requirement tag that exists in "{path}"'))
def features_traced(path: str) -> None:
    ids = {r["id"] for r in traceability.load_requirements(ROOT / path)}
    problems = {
        f: reqs for f, reqs in traceability.feature_requirements().items() if not reqs or set(reqs) - ids
    }
    assert not problems, f"features without a valid requirement tag: {problems}"


@given("a test run reported these scenario results:", target_fixture="cucumber_file")
def cucumber_results(tmp_path: Path, datatable: list[list[str]]) -> Path:
    header, *rows = datatable
    features: dict[str, dict[str, Any]] = {}
    for row in rows:
        spec = dict(zip(header, row, strict=True))
        feature = features.setdefault(spec["feature"], {"uri": spec["feature"], "tags": [], "elements": []})
        feature["elements"].append(
            {
                "name": spec["scenario"],
                "tags": [{"name": f"@{spec['requirement']}"}],
                "steps": [{"result": {"status": spec["status"]}}],
            }
        )
    path = tmp_path / "cucumber.json"
    path.write_text(json.dumps(list(features.values())), encoding="utf-8")
    return path


@when("the traceability matrix is built")
def matrix_built(cucumber_file: Path, ctx: dict[str, Any], tmp_path: Path) -> None:
    ctx["matrix"] = traceability.build_matrix(cucumber_file)
    ctx["matrix_csv"] = traceability.write_matrix(ctx["matrix"], tmp_path)
    ctx["matrix_html_rows"] = traceability.as_report_rows(ctx["matrix"])


@then("the matrix shows these requirement statuses:")
def matrix_statuses(ctx: dict[str, Any], datatable: list[list[str]]) -> None:
    statuses = {row.requirement["id"]: row.status for row in ctx["matrix"]}
    expected = {row[0]: row[1] for row in datatable[1:]}
    assert {k: statuses[k] for k in expected} == expected
    assert ctx["matrix_csv"].exists()
    assert {r["id"]: r["status"] for r in ctx["matrix_html_rows"]}.items() >= expected.items()


@given("the reports of a finished test run", target_fixture="reports")
def finished_reports(tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    reports.mkdir()
    for name in evidence.REPORT_FILES:
        (reports / name).write_text(f"content of {name}", encoding="utf-8")
    return reports


@when("an evidence pack is created from them")
def create_pack(reports: Path, ctx: dict[str, Any], db: SqlClient) -> None:
    ctx["pack"] = evidence.create_pack(reports, reports.parent / "evidence", db.scalar("SHOW server_version"))


@then("its manifest holds a SHA-256 hash for every report, the git commit and the pinned package versions")
def manifest_complete(ctx: dict[str, Any]) -> None:
    manifest = json.loads((ctx["pack"] / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["files"]) == set(evidence.REPORT_FILES)
    assert all(len(h) == 64 for h in manifest["files"].values())
    assert manifest["git_commit"] and manifest["constraints_sha256"] and manifest["database"] != "unknown"


@then("verifying the pack finds no change")
def pack_intact(ctx: dict[str, Any]) -> None:
    assert evidence.verify_pack(ctx["pack"]) == []


@when(parsers.parse('someone edits "{name}" inside the pack'))
def tamper(ctx: dict[str, Any], name: str) -> None:
    file = ctx["pack"] / name
    file.write_text(file.read_text(encoding="utf-8") + " edited", encoding="utf-8")


@then(parsers.parse('verifying the pack names "{name}" as changed'))
def pack_tampered(ctx: dict[str, Any], name: str) -> None:
    assert evidence.verify_pack(ctx["pack"]) == [f"{name}: changed since the pack was created"]

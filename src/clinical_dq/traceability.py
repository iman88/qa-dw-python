"""Requirements traceability: which scenarios verify which requirement, and did they pass.

Requirements live in docs/requirements.json; every feature carries @REQ_xx tags. After a
run, the scenario results become the Requirements section of reports/data-quality-report.html and,
for auditors, reports/traceability-matrix.csv: one row per requirement with its scenarios and outcome. Regulated (GxP) teams need exactly this to show
that every requirement was tested, and how it went.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from clinical_dq.config import ROOT

REQUIREMENTS = ROOT / "docs" / "requirements.json"
FEATURES = ROOT / "tests" / "features"
REQ_TAG = re.compile(r"@(REQ_\d+)")


def load_requirements(path: Path = REQUIREMENTS) -> list[dict[str, str]]:
    return json.loads(path.read_text(encoding="utf-8"))["requirements"]


def feature_requirements(features: Path = FEATURES) -> dict[str, list[str]]:
    """Feature file name -> the requirement ids in its first tag line."""
    found = {}
    for feature in sorted(features.glob("*.feature")):
        first = feature.read_text(encoding="utf-8").split("\n", 1)[0]
        found[feature.name] = REQ_TAG.findall(first)
    return found


@dataclass
class TraceRow:
    requirement: dict[str, str]
    scenarios: list[dict[str, str]] = field(default_factory=list)

    @property
    def status(self) -> str:
        if not self.scenarios:
            return "NOT TESTED"
        if any(s["status"] == "failed" for s in self.scenarios):
            return "FAILED"
        if all(s["status"] == "passed" for s in self.scenarios):
            return "PASSED"
        return "PARTLY RUN"


def _scenario_status(element: dict[str, Any]) -> str:
    statuses = [step.get("result", {}).get("status", "skipped") for step in element.get("steps", [])]
    if "failed" in statuses:
        return "failed"
    if statuses and all(s == "passed" for s in statuses):
        return "passed"
    return "skipped"


def build_matrix(cucumber_json: Path, requirements: list[dict[str, str]] | None = None) -> list[TraceRow]:
    requirements = requirements or load_requirements()
    rows = {r["id"]: TraceRow(r) for r in requirements}
    for feature in json.loads(cucumber_json.read_text(encoding="utf-8")):
        feature_tags = [t["name"] for t in feature.get("tags", [])]
        for element in feature.get("elements", []):
            tags = feature_tags + [t["name"] for t in element.get("tags", [])]
            scenario = {
                "feature": Path(feature.get("uri", "")).name,
                "scenario": element.get("name", ""),
                "status": _scenario_status(element),
            }
            for req in {m for t in tags for m in REQ_TAG.findall(t)}:
                if req in rows:
                    rows[req].scenarios.append(scenario)
    return list(rows.values())


def build_matrix_from_results(
    results: list[dict[str, Any]], requirements: list[dict[str, str]] | None = None
) -> list[TraceRow]:
    """Same matrix from pytest's own results (works with parallel runs, where cucumber.json stays empty).

    Each result: {"scenario", "feature", "status", "requirements": ["REQ_01", ...]}.
    """
    requirements = requirements or load_requirements()
    rows = {r["id"]: TraceRow(r) for r in requirements}
    for result in results:
        for req in result["requirements"]:
            if req in rows:
                rows[req].scenarios.append(
                    {"feature": result["feature"], "scenario": result["scenario"], "status": result["status"]}
                )
    return list(rows.values())


def write_matrix(rows: list[TraceRow], out_dir: Path) -> Path:
    """The auditor's copy: reports/traceability-matrix.csv. The same matrix is a section of the HTML report."""
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "traceability-matrix.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["requirement", "title", "status", "feature", "scenario", "scenario_status"])
        for row in rows:
            for s in row.scenarios or [{"feature": "", "scenario": "", "status": ""}]:
                writer.writerow(
                    [
                        row.requirement["id"],
                        row.requirement["title"],
                        row.status,
                        s["feature"],
                        s["scenario"],
                        s["status"],
                    ]
                )
    return csv_path


def as_report_rows(rows: list[TraceRow]) -> list[dict[str, Any]]:
    """The matrix as plain data for the Requirements section of the HTML report."""
    return [
        {
            "id": r.requirement["id"],
            "title": r.requirement["title"],
            "text": r.requirement["text"],
            "status": r.status,
            "passed": sum(1 for s in r.scenarios if s["status"] == "passed"),
            "total": len(r.scenarios),
            "features": sorted({s["feature"] for s in r.scenarios if s["feature"]}),
        }
        for r in rows
    ]

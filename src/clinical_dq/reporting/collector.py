"""Collects results during a run and writes the data quality report (JSON + HTML).

This is the one HTML report of a run. It shows the requirements and the *data*: every
reconciliation with its counts and sample differences, every DQ rule with offending
rows, the layer build stats, and the GenAI evaluation scores. It is the page you send
to a data engineer when something breaks.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

from jinja2 import Environment, select_autoescape


class ReportCollector:
    def __init__(self) -> None:
        self.build: dict[str, Any] = {}
        self.recon: dict[str, dict[str, Any]] = {}
        self.dq: dict[str, dict[str, Any]] = {}
        self.genai: list[dict[str, Any]] = []
        self.mutations: list[dict[str, Any]] = []
        self.requirements: list[dict[str, Any]] = []

    def add_recon(self, result: Any) -> None:
        self.recon[result.name] = result.to_dict()

    def add_dq(self, result: Any) -> None:
        self.dq[result.name] = result.to_dict()

    def add_genai(self, result: Any, expected_failure: bool = False) -> None:
        """expected_failure: a deliberately bad output (test double) that the evaluator must flag."""
        data = result.to_dict()
        data["expected_failure"] = expected_failure
        data["score_ok"] = (not data["passed"]) if expected_failure else data["passed"]
        self.genai.append(data)

    def add_mutation(
        self, defect: str, story: str, expected_check: str, caught: bool, caught_by: list[str]
    ) -> None:
        self.mutations.append(
            {
                "defect": defect,
                "story": story,
                "expected_check": expected_check,
                "caught": caught,
                "caught_by": caught_by,
            }
        )

    # ---- parallel runs: each pytest-xdist worker saves its part, the controller merges them
    def write_part(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        part = {
            "build": self.build,
            "recon": self.recon,
            "dq": self.dq,
            "genai": self.genai,
            "mutations": self.mutations,
        }
        path.write_text(json.dumps(part, default=str), encoding="utf-8")

    def merge_parts(self, folder: Path) -> None:
        for part_file in sorted(folder.glob("*.json")):
            part = json.loads(part_file.read_text(encoding="utf-8"))
            self.build = self.build or part["build"]
            self.recon.update(part["recon"])
            self.dq.update(part["dq"])
            self.genai.extend(part["genai"])
            self.mutations.extend(part["mutations"])

    def payload(self) -> dict[str, Any]:
        def score(items: list[dict[str, Any]]) -> dict[str, int]:
            def ok(i: dict[str, Any]) -> bool:
                return bool(i.get("score_ok", i.get("passed", i.get("caught"))))

            return {"total": len(items), "passed": sum(1 for i in items if ok(i))}

        metrics: dict[str, dict[str, int]] = {}
        for case in (c for c in self.genai if not c["expected_failure"]):
            for name, ok in case["metrics"].items():
                m = metrics.setdefault(name, {"passed": 0, "total": 0})
                m["total"] += 1
                m["passed"] += int(ok)
        return {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "build": self.build,
            "summary": {
                "reconciliation": score(list(self.recon.values())),
                "data_quality": score(list(self.dq.values())),
                "mutations": score(self.mutations),
                "genai_cases": score(self.genai),
                "requirements": {
                    "total": len(self.requirements),
                    "passed": sum(1 for r in self.requirements if r["status"] == "PASSED"),
                },
            },
            "requirements": self.requirements,
            "reconciliation": sorted(self.recon.values(), key=lambda r: (r["passed"], r["name"])),
            "data_quality": sorted(self.dq.values(), key=lambda r: (r["passed"], r["layer"], r["name"])),
            "mutations": self.mutations,
            "genai": self.genai,
            "genai_metrics": metrics,
        }

    def write(self, out_dir: Path) -> Path | None:
        if not (self.recon or self.dq or self.genai or self.mutations or self.requirements):
            return None
        out_dir.mkdir(parents=True, exist_ok=True)
        data = self.payload()
        (out_dir / "data-quality-report.json").write_text(
            json.dumps(data, indent=2, default=str), encoding="utf-8"
        )
        template = (
            resources.files("clinical_dq.reporting.templates").joinpath("report.html").read_text("utf-8")
        )
        env = Environment(autoescape=select_autoescape(["html"]))
        html = env.from_string(template).render(**data, data_json=json.dumps(data, default=str))
        target = out_dir / "data-quality-report.html"
        target.write_text(html, encoding="utf-8")
        return target

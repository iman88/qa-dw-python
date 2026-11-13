"""Evidence packs: a run's reports frozen with SHA-256 hashes and the environment that produced them.

`clinical-dq evidence` copies the reports into reports/evidence/<pack>/ and writes manifest.json:
the hash of every file, the pinned package versions (constraints.txt hash), the Python and database
versions, and the git commit. `verify` recomputes every hash, so any later change to a retained
report is detected. This is the kind of record GxP validation and audits ask for.
"""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from clinical_dq.config import ROOT

REPORT_FILES = (
    "data-quality-report.html",
    "data-quality-report.json",
    "cucumber.json",
    "traceability-matrix.csv",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except OSError, subprocess.CalledProcessError:
        return "no commit"


def create_pack(reports: Path, out_dir: Path, database_version: str = "unknown") -> Path:
    created = datetime.now(UTC)
    pack = out_dir / f"evidence-{created:%Y%m%dT%H%M%SZ}"
    pack.mkdir(parents=True)
    files = {}
    for name in REPORT_FILES:
        if (reports / name).exists():
            shutil.copy2(reports / name, pack / name)
            files[name] = sha256(pack / name)
    constraints = ROOT / "constraints.txt"
    manifest: dict[str, Any] = {
        "created_at": created.isoformat(),
        "git_commit": _git_commit(),
        "python": platform.python_version(),
        "database": database_version,
        "constraints_sha256": sha256(constraints) if constraints.exists() else None,
        "files": files,
    }
    (pack / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return pack


def verify_pack(pack: Path) -> list[str]:
    """Files whose content no longer matches the manifest (or that are missing). Empty = intact."""
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    problems = []
    for name, expected in manifest["files"].items():
        file = pack / name
        if not file.exists():
            problems.append(f"{name}: missing")
        elif sha256(file) != expected:
            problems.append(f"{name}: changed since the pack was created")
    return problems

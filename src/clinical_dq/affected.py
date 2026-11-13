"""Which tests a change can affect, so CI runs only those.

Every feature names the SQL files it runs, so the mapping is mostly a text search:

* a file named in a feature (or in a folder a feature names) selects that feature's tags;
* a change to anything shared (the build scripts, the Python package, the step definitions, the
  pinned dependencies) can affect anything, so everything runs;
* documentation-only changes select nothing.

    clinical-dq affected --since origin/main      ->  pytest -m "recon or mutation"
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path, PurePosixPath

from clinical_dq.config import ROOT

FEATURES = ROOT / "tests" / "features"
EVERYTHING = (
    "sql/build/",
    "sql/incremental/",
    "src/",
    "tests/steps/",
    "tests/conftest.py",
    "conftest.py",
    "pyproject.toml",
    "constraints.txt",
    "docker-compose.yml",
    "sql/contracts/",
)
NOTHING = (".md", ".png", ".claude/", "docs/", "LICENSE", "NOTICE")
TAG = re.compile(r"^@(.+)$", re.MULTILINE)


def _feature_tags(text: str) -> list[str]:
    first = TAG.search(text)
    return [t.lstrip("@") for t in first.group(0).split() if t != "@all"] if first else []


def affected_markers(changed: list[str], features: Path = FEATURES) -> list[str] | None:
    """Pytest markers to run for these changed paths. None means "run everything"."""
    paths = [p.replace("\\", "/") for p in changed]
    if any(p.startswith(EVERYTHING) or p in EVERYTHING for p in paths):
        return None
    relevant = [p for p in paths if not p.endswith(NOTHING) and not p.startswith(NOTHING)]
    markers: set[str] = set()
    for feature in sorted(features.glob("*.feature")):
        text = feature.read_text(encoding="utf-8")
        if feature.as_posix().endswith(tuple(relevant)):
            markers.update(_feature_tags(text))
            continue
        named = set(re.findall(r"sql/[\w/.-]+", text))
        for path in relevant:
            if any(
                path == n or path.startswith(n.rstrip("/") + "/") or str(PurePosixPath(path).parent) == n
                for n in named
            ):
                markers.update(_feature_tags(text))
    return sorted(markers)


def changed_since(ref: str) -> list[str]:
    """Files changed since ``ref`` plus uncommitted and untracked ones."""

    def git(*args: str) -> list[str]:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        return [line for line in out.splitlines() if line]

    return sorted(
        set(git("diff", "--name-only", ref)) | set(git("ls-files", "--others", "--exclude-standard"))
    )


def pytest_command(markers: list[str] | None) -> str:
    if markers is None:
        return "pytest"
    if not markers:
        return "# nothing to run: no test depends on the changed files"
    return f'pytest -m "{" or ".join(markers)}"'

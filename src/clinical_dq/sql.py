"""Loads and renders the SQL files in the repo-root ``sql/`` folder. One query or script per file.

Paths are written from the repo root, exactly as they appear in the feature files and reports,
for example ``sql/checks/rules/keys/referential_integrity.sql``.

Placeholders in a file:
  {src} {raw} {hist} {latest} {dwh}   layer schemas (prefixed ``mut_`` in a mutation build)
  {table} {key} {columns} ...         identifiers passed by the caller (a database cannot bind them)
  :name                               bind parameters, passed to the driver at execution time

Identifiers only ever come from the repo (features, catalogues), never from user input.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from typing import Any

from clinical_dq.config import ROOT
from clinical_dq.layers import DEFAULT, Layers

SQL_ROOT = ROOT / "sql"
_BIND = re.compile(r"(?<!:):([a-zA-Z_]\w*)")


def resolve(path: str) -> Path:
    relative = path.replace("\\", "/").removeprefix("sql/")
    file = SQL_ROOT / relative
    if not file.exists():
        raise FileNotFoundError(f"SQL file not found: sql/{relative}")
    return file


@cache
def load(path: str) -> str:
    return resolve(path).read_text(encoding="utf-8")


def render(text: str, layers: Layers = DEFAULT, **identifiers: Any) -> str:
    """Fill identifiers first (they may contain layer placeholders), then layer schemas."""
    for key, value in identifiers.items():
        text = text.replace("{" + key + "}", str(value))
    return layers.render(text)


def sql(path: str, layers: Layers = DEFAULT, **identifiers: Any) -> str:
    return render(load(path), layers, **identifiers)


def bind_params(text: str, values: dict[str, Any]) -> dict[str, Any]:
    """The subset of ``values`` that the query actually binds (``:name``)."""
    wanted = set(_BIND.findall(text))
    return {k: v for k, v in values.items() if k in wanted}


def description(path: str, **identifiers: Any) -> str:
    """The first comment line of a file, rendered: the human description of a check or defect."""
    for line in load(path).splitlines():
        if line.strip().startswith("--"):
            text = render(line.strip().removeprefix("--").strip(), DEFAULT, **identifiers).removeprefix(
                "Rule: "
            )
            return text[:1].upper() + text[1:]
    return path


def files(folder: str, recursive: bool = True) -> list[str]:
    """.sql files in a folder and its category subfolders, as repo-relative paths sorted by path."""
    directory = resolve(folder)
    found = directory.rglob("*.sql") if recursive else directory.glob("*.sql")
    return sorted(f"sql/{p.relative_to(SQL_ROOT).as_posix()}" for p in found)

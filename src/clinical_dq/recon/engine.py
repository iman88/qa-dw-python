"""Reconciliation: compare two row sets by business key, column by column.

``diff_rows`` is a pure function (no database), so it is unit tested on its own. The
same engine handles row-level checks (every adverse event) and aggregate checks
(serious events per study): an aggregate is just a grouped query keyed by the group.

At real volumes you would push this down into SQL (hash per row, compare hashes, then
drill into mismatching keys). The result object stays the same.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

SAMPLE = 20


def normalise(value: Any) -> Any:
    """Make values from different layers comparable (Decimal vs float, date vs datetime...)."""
    if isinstance(value, Decimal):
        return round(float(value), 6)
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value.strip()
    return value


@dataclass
class ReconResult:
    name: str
    key: tuple[str, ...]
    source_count: int
    target_count: int
    missing_in_target: list[Any] = field(default_factory=list)
    extra_in_target: list[Any] = field(default_factory=list)
    duplicate_in_source: list[Any] = field(default_factory=list)
    duplicate_in_target: list[Any] = field(default_factory=list)
    mismatches: list[dict[str, Any]] = field(default_factory=list)
    compared_columns: tuple[str, ...] = ()
    description: str = ""
    stats: dict[str, Any] = field(
        default_factory=dict
    )  # how the comparison ran (engine, buckets, rows fetched)

    @property
    def passed(self) -> bool:
        return (
            self.source_count == self.target_count
            and not self.missing_in_target
            and not self.extra_in_target
            and not self.duplicate_in_source
            and not self.duplicate_in_target
            and not self.mismatches
        )

    def summary(self) -> str:
        if self.passed:
            return (
                f"{self.name}: OK ({self.source_count} rows, {len(self.compared_columns)} columns compared)"
            )
        parts = [f"source={self.source_count}", f"target={self.target_count}"]
        for label, items in (
            ("missing_in_target", self.missing_in_target),
            ("extra_in_target", self.extra_in_target),
            ("duplicate_in_source", self.duplicate_in_source),
            ("duplicate_in_target", self.duplicate_in_target),
            ("mismatched_values", self.mismatches),
        ):
            if items:
                parts.append(f"{label}={len(items)} e.g. {items[:3]}")
        return f"{self.name}: FAILED - " + "; ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "stats": self.stats,
            "passed": self.passed,
            "key": list(self.key),
            "compared_columns": list(self.compared_columns),
            "source_count": self.source_count,
            "target_count": self.target_count,
            "missing_in_target": [_plain(k) for k in self.missing_in_target[:SAMPLE]],
            "extra_in_target": [_plain(k) for k in self.extra_in_target[:SAMPLE]],
            "duplicate_in_source": [_plain(k) for k in self.duplicate_in_source[:SAMPLE]],
            "duplicate_in_target": [_plain(k) for k in self.duplicate_in_target[:SAMPLE]],
            "mismatches": self.mismatches[:SAMPLE],
            "counts": {
                "missing_in_target": len(self.missing_in_target),
                "extra_in_target": len(self.extra_in_target),
                "duplicate_in_source": len(self.duplicate_in_source),
                "duplicate_in_target": len(self.duplicate_in_target),
                "mismatches": len(self.mismatches),
            },
        }


def _plain(key: Any) -> Any:
    return (
        key[0] if isinstance(key, tuple) and len(key) == 1 else list(key) if isinstance(key, tuple) else key
    )


def diff_rows(
    name: str,
    source_rows: list[dict[str, Any]],
    target_rows: list[dict[str, Any]],
    key: tuple[str, ...] | list[str],
    columns: tuple[str, ...] | list[str] | None = None,
    description: str = "",
) -> ReconResult:
    key = tuple(key)
    if columns is None:
        names = source_rows[0].keys() if source_rows else target_rows[0].keys() if target_rows else ()
        columns = tuple(c for c in names if c not in key)
    columns = tuple(columns)

    def index(rows: list[dict[str, Any]]) -> tuple[dict[tuple, dict[str, Any]], list[tuple]]:
        keys = [tuple(normalise(r[k]) for k in key) for r in rows]
        counts = Counter(keys)
        return dict(zip(keys, rows, strict=True)), sorted(k for k, n in counts.items() if n > 1)

    src, dup_src = index(source_rows)
    tgt, dup_tgt = index(target_rows)

    result = ReconResult(
        name=name,
        key=key,
        source_count=len(source_rows),
        target_count=len(target_rows),
        missing_in_target=sorted(src.keys() - tgt.keys()),
        extra_in_target=sorted(tgt.keys() - src.keys()),
        duplicate_in_source=dup_src,
        duplicate_in_target=dup_tgt,
        compared_columns=columns,
        description=description,
    )
    for k in sorted(src.keys() & tgt.keys()):
        for col in columns:
            s, t = normalise(src[k].get(col)), normalise(tgt[k].get(col))
            if s != t:
                result.mismatches.append({"key": _plain(k), "column": col, "source": s, "target": t})
    return result

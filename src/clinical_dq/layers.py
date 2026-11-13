"""Schema names for one build of the pipeline.

A build has five layers. The default build uses plain names; mutation tests use a
prefix (for example ``mut_``) so they can break a copy without touching the main one.

    src     operational source system, current state only (system of record)
    raw     landing zone: at-least-once CDC feed, duplicates included, partitioned by ingest month
    hist    full history: one row per real change, SCD2 validity ranges, deletes kept
    latest  current state: latest version per key, deduplicated, deletes removed
    dwh     star schema: dimensions + facts partitioned by event month
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Layers:
    prefix: str = ""

    @property
    def src(self) -> str:
        return f"{self.prefix}src"

    @property
    def raw(self) -> str:
        return f"{self.prefix}raw"

    @property
    def hist(self) -> str:
        return f"{self.prefix}hist"

    @property
    def latest(self) -> str:
        return f"{self.prefix}latest"

    @property
    def dwh(self) -> str:
        return f"{self.prefix}dwh"

    def all(self) -> list[str]:
        return [self.src, self.raw, self.hist, self.latest, self.dwh]

    def render(self, sql: str) -> str:
        """Fill {src}/{raw}/{hist}/{latest}/{dwh} placeholders. Other braces are left alone."""
        for name in ("src", "raw", "hist", "latest", "dwh"):
            sql = sql.replace("{" + name + "}", getattr(self, name))
        return sql


DEFAULT = Layers()
MUTATION = Layers(prefix="mut_")

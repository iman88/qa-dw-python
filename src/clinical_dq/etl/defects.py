"""Known pipeline bugs, injected on purpose into the mutation build.

Each defect is one file in ``sql/defects/``; its first comment line is the story (the real cause
it imitates). A defect is identified by its path, e.g. ``sql/defects/orphan_fact.sql``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from clinical_dq import sql
from clinical_dq.db.client import SqlClient
from clinical_dq.layers import Layers

FOLDER = "sql/defects"


@dataclass(frozen=True)
class Defect:
    path: str
    story: str

    @property
    def name(self) -> str:
        return PurePosixPath(self.path).stem


DEFECTS: dict[str, Defect] = {PurePosixPath(p).stem: Defect(p, sql.description(p)) for p in sql.files(FOLDER)}
BY_PATH = {d.path: d for d in DEFECTS.values()}


def inject(db: SqlClient, layers: Layers, name_or_path: str) -> int:
    defect = BY_PATH.get(name_or_path) or DEFECTS[PurePosixPath(name_or_path).stem]
    affected = db.execute(sql.sql(defect.path, layers))
    if affected == 0:
        raise AssertionError(f"{defect.path} changed no rows; the seeded data no longer exercises it")
    return affected

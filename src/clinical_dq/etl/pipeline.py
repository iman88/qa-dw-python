"""Builds every layer by running the scripts in ``sql/build`` in file-name order.

    landing/     00-01  src (operational system) and raw (partitioned CDC feed); data loads after 01
    history/     10-12  full history per entity, plus a current-state view per entity
    latest/      20-21  deduplicated current state per entity, read straight from raw
    dimensions/  30-34  dwh schema and dimensions
    facts/       40-41  monthly-partitioned facts
    views/       50-52  reporting views

Scripts run in order of their number prefix, across category folders.

A file whose name ends in ``_entity.sql`` is a template and runs once per entity
(study, site, subject, visit, adverse_event) with {entity}, {key}, {columns},
{events_table} and {history_table} filled in.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import PurePosixPath

from clinical_dq import sql
from clinical_dq.data.entities import ENTITIES, Entity
from clinical_dq.data.generator import GeneratedData, generate
from clinical_dq.db.client import SqlClient
from clinical_dq.layers import DEFAULT, Layers

log = logging.getLogger("clinical_dq.etl")
BUILD = "sql/build"
INCREMENTAL = "sql/incremental"
DEFAULT_CUTOFF = datetime(2026, 1, 1, tzinfo=UTC)  # events ingested from here on form the incremental batch
LOAD_AFTER = "01_raw.sql"  # generated data is inserted once this script has created the raw tables


def entity_params(entity: Entity) -> dict[str, str]:
    return {
        "entity": entity.name,
        "key": entity.key,
        "columns": ", ".join(entity.columns),
        "events_table": entity.events_table,
        "history_table": entity.history_table,
        "raw_columns": ", ".join(f"r.{c}" for c in entity.columns),
        "source_columns": ", ".join(f"s.{c}" for c in entity.columns),
        "set_columns": ", ".join(f"{c} = s.{c}" for c in entity.non_key_columns),
    }


def render_script(path: str, layers: Layers, **extra: str) -> str:
    if PurePosixPath(path).stem.endswith("_entity"):
        return "\n".join(sql.sql(path, layers, **entity_params(e), **extra) for e in ENTITIES)
    return sql.sql(path, layers, **extra)


@dataclass
class BuildReport:
    layers: Layers
    stats: dict[str, int] = field(default_factory=dict)
    timings_ms: dict[str, float] = field(default_factory=dict)
    scripts: list[str] = field(default_factory=list)


def load_data(
    db: SqlClient, layers: Layers, data: GeneratedData, ingested_before: datetime | None = None
) -> None:
    """Load the source system and the feed; with ``ingested_before`` only the events that had arrived by then."""
    for entity in ENTITIES:  # parents before children so the source constraints hold
        db.insert_many(f"{layers.src}.{entity.name}", data.source[entity.name])
        feed = data.feed[entity.name]
        if ingested_before is not None:
            feed = [e for e in feed if e["ingested_at"] < ingested_before]
        db.insert_many(f"{layers.raw}.{entity.events_table}", feed)


def load_batch(db: SqlClient, layers: Layers, data: GeneratedData, ingested_from: datetime) -> int:
    """Land the events that arrived from ``ingested_from`` onwards (the next batch) in raw."""
    landed = 0
    for entity in ENTITIES:
        batch = [e for e in data.feed[entity.name] if e["ingested_at"] >= ingested_from]
        landed += db.insert_many(f"{layers.raw}.{entity.events_table}", batch)
    return landed


def build_scripts(first_prefix: str = "00") -> list[str]:
    """Build scripts in number order, starting at ``first_prefix`` (e.g. "30" = the star schema onwards)."""
    scripts = sorted(sql.files(BUILD), key=lambda p: PurePosixPath(p).name)
    return [p for p in scripts if PurePosixPath(p).name >= first_prefix]


def apply_increment(db: SqlClient, layers: Layers, batch_start: datetime) -> None:
    """Fold a landed batch into hist and latest (sql/incremental/), then refresh the star schema."""
    stamp = batch_start.isoformat(sep=" ")
    for path in sorted(sql.files(INCREMENTAL), key=lambda p: PurePosixPath(p).name):
        db.execute_script(render_script(path, layers, batch_start=stamp))
    for path in build_scripts(first_prefix="30"):
        db.execute_script(render_script(path, layers))


def run_incremental(
    db: SqlClient,
    layers: Layers,
    seed: int = 42,
    subjects_per_study: int = 40,
    cutoff: datetime | None = None,
) -> BuildReport:
    """Full build from the events that arrived before ``cutoff``, then the rest as one incremental batch.

    The result must equal a full build of everything: that is what the incremental feature checks.
    """
    cutoff = cutoff or DEFAULT_CUTOFF
    report = BuildReport(layers=layers)
    data = generate(seed, subjects_per_study)
    report.stats.update(data.stats)
    for path in build_scripts():
        db.execute_script(render_script(path, layers))
        if PurePosixPath(path).name == LOAD_AFTER:
            load_data(db, layers, data, ingested_before=cutoff)
    report.stats["incremental_batch_events"] = load_batch(db, layers, data, cutoff)
    apply_increment(db, layers, cutoff)
    return report


def run(db: SqlClient, layers: Layers = DEFAULT, seed: int = 42, subjects_per_study: int = 40) -> BuildReport:
    report = BuildReport(layers=layers)
    started = time.perf_counter()
    data = generate(seed, subjects_per_study)
    report.stats.update(data.stats)
    report.timings_ms["generate"] = round((time.perf_counter() - started) * 1000, 1)

    for path in build_scripts():
        name = PurePosixPath(path).name
        stage = PurePosixPath(path).parent.name
        started = time.perf_counter()
        db.execute_script(render_script(path, layers))
        if name == LOAD_AFTER:
            load_data(db, layers, data)
        elapsed = (time.perf_counter() - started) * 1000
        report.timings_ms[stage] = round(report.timings_ms.get(stage, 0) + elapsed, 1)
        report.scripts.append(name)
        log.info("ran %s in %.0f ms", name, elapsed)
    return report


def drop(db: SqlClient, layers: Layers) -> None:
    db.execute_script("\n".join(f"DROP SCHEMA IF EXISTS {s} CASCADE;" for s in layers.all()))

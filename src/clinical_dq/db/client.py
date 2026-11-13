"""Thin SQL client over SQLAlchemy.

Tests talk to the database through this class only, so query logging, timing and
type handling live in one place. Results come back as plain dicts.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import create_engine, make_url, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, ProgrammingError

log = logging.getLogger("clinical_dq.sql")


class SqlClient:
    def __init__(self, url: str, echo: bool = False) -> None:
        self.url = url
        self.engine: Engine = create_engine(url, pool_pre_ping=True, echo=echo)

    # ---- connection -------------------------------------------------------------
    def wait_until_ready(self, timeout_s: float = 60.0) -> None:
        deadline = time.monotonic() + timeout_s
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                self.scalar("SELECT 1")
                return
            except OperationalError as exc:  # container still starting
                last_error = exc
                time.sleep(1)
        raise RuntimeError(
            f"Database not reachable at {self.safe_url} after {timeout_s:.0f}s. "
            "Start it with: docker compose up -d"
        ) from last_error

    @property
    def safe_url(self) -> str:
        return self.engine.url.render_as_string(hide_password=True)

    # ---- reads ------------------------------------------------------------------
    def query(self, sql: str, params: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
        started = time.perf_counter()
        with self.engine.connect() as conn:
            rows = [dict(r._mapping) for r in conn.execute(text(sql), params or {})]
        log.debug("%d rows in %.1f ms: %s", len(rows), (time.perf_counter() - started) * 1000, _short(sql))
        return rows

    def columns(self, sql: str, params: Mapping[str, Any] | None = None) -> list[str]:
        """Column names a query returns, without fetching any row."""
        with self.engine.connect() as conn:
            return list(conn.execute(text(f"SELECT * FROM ({sql}) AS q LIMIT 0"), params or {}).keys())

    def scalar(self, sql: str, params: Mapping[str, Any] | None = None) -> Any:
        with self.engine.connect() as conn:
            return conn.execute(text(sql), params or {}).scalar()

    def explain(self, sql: str, params: Mapping[str, Any] | None = None) -> str:
        """Plain-text EXPLAIN plan, used to prove partition pruning."""
        rows = self.query(f"EXPLAIN (COSTS OFF) {sql}", params)
        return "\n".join(next(iter(r.values())) for r in rows)

    # ---- writes -----------------------------------------------------------------
    def execute(self, sql: str, params: Mapping[str, Any] | None = None) -> int:
        with self.engine.begin() as conn:
            return conn.execute(text(sql), params or {}).rowcount

    def execute_script(self, script: str) -> None:
        """Run a multi-statement SQL script in one transaction (no bind parameters)."""
        started = time.perf_counter()
        with self.engine.begin() as conn:
            # Raw DB-API cursor with no parameters, so psycopg leaves %-signs and $$ blocks alone.
            conn.connection.cursor().execute(script)
        log.debug("script ran in %.1f ms", (time.perf_counter() - started) * 1000)

    def insert_many(self, table: str, rows: Sequence[Mapping[str, Any]]) -> int:
        if not rows:
            return 0
        columns = list(rows[0].keys())
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(':' + c for c in columns)})"
        with self.engine.begin() as conn:
            conn.execute(text(sql), list(rows))
        return len(rows)

    def rollback_probe(
        self, statement: str, probe: str, params: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run ``statement``, read the effect with ``probe``, then roll everything back.

        Lets a test write into the real warehouse (for example to see which partition a row
        lands in) without leaving anything behind.
        """
        with self.engine.connect() as conn:
            tx = conn.begin()
            try:
                conn.execute(text(statement), params or {})
                return [dict(r._mapping) for r in conn.execute(text(probe), params or {})]
            finally:
                tx.rollback()

    def allowed_as_role(self, role: str, sql: str) -> bool:
        """Whether ``role`` may run ``sql``. Runs inside a transaction that is always rolled back."""
        with self.engine.connect() as conn:
            tx = conn.begin()
            try:
                conn.execute(text(f"SET LOCAL ROLE {role}"))
                conn.execute(text(sql)).fetchall()
                return True
            except ProgrammingError as exc:
                if "permission denied" in str(exc).lower():
                    return False
                raise
            finally:
                tx.rollback()

    def dispose(self) -> None:
        self.engine.dispose()


def isolated_database(url: str, suffix: str) -> str:
    """URL of a database named ``<database>_<suffix>``, created on first use.

    Gives every pytest-xdist worker and every CI run its own database, so parallel runs can never
    see each other's tables. The base database is only used to issue CREATE DATABASE.
    """
    base = make_url(url)
    name = f"{base.database}_{suffix}".lower().replace("-", "_")
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name}).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        admin.dispose()
    return base.set(database=name).render_as_string(hide_password=False)


def _short(sql: str, width: int = 120) -> str:
    flat = " ".join(sql.split())
    return flat if len(flat) <= width else flat[: width - 3] + "..."

"""Push-down reconciliation: compare checksums inside the database, fetch only what differs.

1. Each side's rows are spread over N buckets by a hash of the business key. For each bucket
   the database returns a row count and an order-independent sum of row hashes
   (sql/checks/recon_engine/bucket_checksums.sql). Nothing else leaves the database.
2. Buckets whose count or checksum differ are fetched from both sides
   (sql/checks/recon_engine/rows_in_buckets.sql) and compared column by column with the same
   engine as the full comparison, so the verdict is exact.

A checksum can differ only because two layers print a value differently (5 vs 5.0). That costs a
fetch, never a false failure: the row-level comparison decides. On a clean warehouse no bucket
is fetched at all, so the cost is two aggregate queries whatever the table size.

On BigQuery the same idea uses FARM_FINGERPRINT and BIT_XOR; see sql/dialects/bigquery/.
"""

from __future__ import annotations

from typing import Any

from clinical_dq import sql
from clinical_dq.db.client import SqlClient
from clinical_dq.recon.engine import ReconResult, diff_rows

CHECKSUMS = "sql/checks/recon_engine/bucket_checksums.sql"
ROWS = "sql/checks/recon_engine/rows_in_buckets.sql"


def _text(column: str) -> str:
    return f"coalesce(q.{column}::text, '<null>')"


def _checksums(db: SqlClient, query: str, key_expr: str, row_expr: str, buckets: int) -> dict[int, tuple]:
    rendered = sql.render(
        sql.load(CHECKSUMS), query=query, key_expr=key_expr, row_expr=row_expr, buckets=buckets
    )
    return {r["bucket"]: (r["row_count"], r["row_hash_sum"]) for r in db.query(rendered)}


def _rows(db: SqlClient, query: str, key_expr: str, buckets: int, wanted: list[int]) -> list[dict[str, Any]]:
    rendered = sql.render(sql.load(ROWS), query=query, key_expr=key_expr, buckets=buckets)
    return db.query(rendered, {"buckets": wanted})


def reconcile(
    db: SqlClient,
    name: str,
    source_query: str,
    target_query: str,
    key: tuple[str, ...],
    buckets: int = 64,
    description: str = "",
) -> ReconResult:
    columns = db.columns(source_query)
    key_expr = ", ".join(_text(k) for k in key)
    row_expr = ", ".join(_text(c) for c in columns)

    source = _checksums(db, source_query, key_expr, row_expr, buckets)
    target = _checksums(db, target_query, key_expr, row_expr, buckets)
    differing = sorted(b for b in source.keys() | target.keys() if source.get(b) != target.get(b))

    source_rows = _rows(db, source_query, key_expr, buckets, differing) if differing else []
    target_rows = _rows(db, target_query, key_expr, buckets, differing) if differing else []
    result = diff_rows(
        name,
        source_rows,
        target_rows,
        key,
        columns=[c for c in columns if c not in key],
        description=description,
    )
    result.source_count = sum(c for c, _ in source.values())
    result.target_count = sum(c for c, _ in target.values())
    result.stats = {
        "engine": "pushdown",
        "buckets": buckets,
        "buckets_differing": len(differing),
        "rows_fetched": len(source_rows) + len(target_rows),
        "rows_total": result.source_count + result.target_count,
    }
    return result

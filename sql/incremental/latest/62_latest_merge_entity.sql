-- Incremental latest state for {entity}: for every key the new batch (ingested from {batch_start}) touched, recompute the winning change across all of raw and MERGE it in.
-- Recomputing per key (instead of trusting the batch order) means a late, older change can never overwrite a newer one, and a key whose last change is a delete is removed.

WITH touched AS (
    SELECT DISTINCT {key} FROM {raw}.{events_table} WHERE ingested_at >= timestamptz '{batch_start}'
),
winner AS (
    SELECT DISTINCT ON (r.{key}) r.*
    FROM {raw}.{events_table} r
    JOIN touched t USING ({key})
    ORDER BY r.{key}, r.change_seq DESC, r.ingested_at DESC
)
MERGE INTO {latest}.{entity} AS l
USING winner AS s
   ON l.{key} = s.{key}
WHEN MATCHED AND s.op = 'D' THEN
    DELETE
WHEN MATCHED AND s.change_seq <> l.last_change_seq THEN
    UPDATE SET {set_columns}, last_change_seq = s.change_seq, last_changed_at = s.changed_at
WHEN NOT MATCHED AND s.op <> 'D' THEN
    INSERT ({columns}, last_change_seq, last_changed_at)
    VALUES ({source_columns}, s.change_seq, s.changed_at);

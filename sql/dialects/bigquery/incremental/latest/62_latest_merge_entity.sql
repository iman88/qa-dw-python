-- BigQuery: incremental latest state for {entity}: for every key the batch touched, recompute the winning change across all of raw and MERGE it in.
MERGE {latest}.{entity} l
USING (
    SELECT * EXCEPT (rn)
    FROM (
        SELECT r.*, ROW_NUMBER() OVER (PARTITION BY r.{key} ORDER BY r.change_seq DESC, r.ingested_at DESC) AS rn
        FROM {raw}.{events_table} r
        WHERE r.ingested_at IS NOT NULL
          AND r.{key} IN (SELECT b.{key} FROM {raw}.{events_table} b WHERE b.ingested_at >= TIMESTAMP '{batch_start}')
    )
    WHERE rn = 1
) s
ON l.{key} = s.{key}
WHEN MATCHED AND s.op = 'D' THEN
    DELETE
WHEN MATCHED AND s.change_seq != l.last_change_seq THEN
    UPDATE SET {set_columns}, last_change_seq = s.change_seq, last_changed_at = s.changed_at
WHEN NOT MATCHED AND s.op != 'D' THEN
    INSERT ({columns}, last_change_seq, last_changed_at)
    VALUES ({source_columns}, s.change_seq, s.changed_at);

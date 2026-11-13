-- BigQuery: incremental history for {entity}: append the batch's new changes, then recompute validity only for the keys the batch touched (MERGE replaces Postgres UPDATE ... FROM with a row comparison).
INSERT INTO {hist}.{history_table} ({columns}, change_seq, op, valid_from, valid_to, is_current, is_deleted,
                                    first_ingested_at)
SELECT {raw_columns}, r.change_seq, r.op, r.changed_at, TIMESTAMP '9999-12-31 00:00:00+00', TRUE, r.op = 'D',
       r.ingested_at
FROM {raw}.{events_table} r
WHERE r.ingested_at >= TIMESTAMP '{batch_start}'
  AND r.change_seq NOT IN (SELECT h.change_seq FROM {hist}.{history_table} h)
QUALIFY ROW_NUMBER() OVER (PARTITION BY r.change_seq ORDER BY r.ingested_at) = 1;

MERGE {hist}.{history_table} h
USING (
    SELECT change_seq,
           COALESCE(LEAD(valid_from) OVER w, TIMESTAMP '9999-12-31 00:00:00+00') AS new_valid_to,
           LEAD(valid_from) OVER w IS NULL AS new_is_current
    FROM {hist}.{history_table}
    WHERE {key} IN (SELECT b.{key} FROM {raw}.{events_table} b WHERE b.ingested_at >= TIMESTAMP '{batch_start}')
    WINDOW w AS (PARTITION BY {key} ORDER BY change_seq)
) t
ON h.change_seq = t.change_seq
WHEN MATCHED AND (h.valid_to != t.new_valid_to OR h.is_current != t.new_is_current) THEN
    UPDATE SET valid_to = t.new_valid_to, is_current = t.new_is_current;

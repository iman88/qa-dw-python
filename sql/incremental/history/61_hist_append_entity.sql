-- Incremental history for {entity}: append every change of the new batch (ingested from {batch_start}) that history does not hold yet, then recompute validity only for the keys the batch touched.
-- Redelivered changes are skipped by change_seq, so running the same batch twice changes nothing.

INSERT INTO {hist}.{history_table} ({columns}, change_seq, op, valid_from, valid_to, is_current, is_deleted,
                                    first_ingested_at)
SELECT DISTINCT ON (r.change_seq)
       {raw_columns}, r.change_seq, r.op, r.changed_at, timestamptz '9999-12-31 00:00:00+00', true,
       r.op = 'D', r.ingested_at
FROM {raw}.{events_table} r
WHERE r.ingested_at >= timestamptz '{batch_start}'
  AND NOT EXISTS (SELECT 1 FROM {hist}.{history_table} h WHERE h.change_seq = r.change_seq)
ORDER BY r.change_seq, r.ingested_at;

WITH touched AS (
    SELECT DISTINCT {key} FROM {raw}.{events_table} WHERE ingested_at >= timestamptz '{batch_start}'
),
timeline AS (
    SELECT h.change_seq,
           COALESCE(LEAD(h.valid_from) OVER w, timestamptz '9999-12-31 00:00:00+00') AS new_valid_to,
           LEAD(h.valid_from) OVER w IS NULL AS new_is_current
    FROM {hist}.{history_table} h
    JOIN touched t USING ({key})
    WINDOW w AS (PARTITION BY h.{key} ORDER BY h.change_seq)
)
UPDATE {hist}.{history_table} h
SET valid_to = t.new_valid_to, is_current = t.new_is_current
FROM timeline t
WHERE h.change_seq = t.change_seq
  AND (h.valid_to, h.is_current) IS DISTINCT FROM (t.new_valid_to, t.new_is_current);

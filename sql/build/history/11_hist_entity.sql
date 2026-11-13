-- Full history for one entity (run once per entity: {entity}, key {key}).
-- One row per real change: redelivered copies of the same change_seq collapse to the first
-- delivery. Each version is valid in [valid_from, valid_to); deletes stay as tombstones.

CREATE TABLE {hist}.{history_table} AS
WITH delivered_once AS (
    SELECT DISTINCT ON (change_seq) *
    FROM {raw}.{events_table}
    ORDER BY change_seq, ingested_at
)
SELECT {columns},
       change_seq,
       op,
       changed_at AS valid_from,
       COALESCE(LEAD(changed_at) OVER w, timestamptz '9999-12-31 00:00:00+00') AS valid_to,
       LEAD(changed_at) OVER w IS NULL AS is_current,
       op = 'D' AS is_deleted,
       ingested_at AS first_ingested_at
FROM delivered_once
WINDOW w AS (PARTITION BY {key} ORDER BY change_seq);

CREATE INDEX ON {hist}.{history_table} ({key}, valid_from);

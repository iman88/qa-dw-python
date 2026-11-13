-- Current state for one entity ({entity}, key {key}), read straight from raw.
-- Latest change per key wins (by change_seq, not arrival time), redelivered copies collapse,
-- and a key whose last change is a delete drops out. No unique constraint on purpose:
-- lake tables rarely enforce one, so uniqueness is tested instead.

CREATE TABLE {latest}.{entity} AS
WITH ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY {key} ORDER BY change_seq DESC, ingested_at DESC) AS rn
    FROM {raw}.{events_table}
)
SELECT {columns}, change_seq AS last_change_seq, changed_at AS last_changed_at
FROM ranked
WHERE rn = 1 AND op <> 'D';

CREATE INDEX ON {latest}.{entity} ({key});

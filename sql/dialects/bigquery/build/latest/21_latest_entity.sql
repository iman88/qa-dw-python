-- BigQuery: current state for {entity}: the latest change per key wins, deleted keys drop out.
CREATE OR REPLACE TABLE {latest}.{entity}
CLUSTER BY {key} AS
SELECT {columns}, last_change_seq, last_changed_at
FROM (
    SELECT {columns}, op, change_seq AS last_change_seq, changed_at AS last_changed_at,
           ROW_NUMBER() OVER (PARTITION BY {key} ORDER BY change_seq DESC, ingested_at DESC) AS rn
    FROM {raw}.{events_table}
    WHERE ingested_at IS NOT NULL
)
WHERE rn = 1 AND op <> 'D';

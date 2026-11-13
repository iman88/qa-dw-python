-- BigQuery: full history for {entity}. QUALIFY replaces Postgres DISTINCT ON to keep the first delivery of each change.
CREATE OR REPLACE TABLE {hist}.{history_table}
CLUSTER BY {key} AS
WITH delivered_once AS (
    SELECT *
    FROM {raw}.{events_table}
    WHERE ingested_at IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (PARTITION BY change_seq ORDER BY ingested_at) = 1
)
SELECT {columns},
       change_seq,
       op,
       changed_at AS valid_from,
       COALESCE(LEAD(changed_at) OVER w, TIMESTAMP '9999-12-31 00:00:00+00') AS valid_to,
       LEAD(changed_at) OVER w IS NULL AS is_current,
       op = 'D' AS is_deleted,
       ingested_at AS first_ingested_at
FROM delivered_once
WINDOW w AS (PARTITION BY {key} ORDER BY change_seq);

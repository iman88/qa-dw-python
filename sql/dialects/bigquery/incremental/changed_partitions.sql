-- BigQuery only: partitions of {table} modified since @since, from INFORMATION_SCHEMA.PARTITIONS. Incremental reconciliation compares only these, instead of every partition every night.
SELECT partition_id, total_rows, last_modified_time
FROM {schema}.INFORMATION_SCHEMA.PARTITIONS
WHERE table_name = '{table}' AND last_modified_time >= @since
ORDER BY partition_id

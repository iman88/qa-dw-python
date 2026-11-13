-- BigQuery: the partitioning column of every partitioned table in one dataset.
SELECT table_name AS object_name, column_name AS partition_key
FROM {schema}.INFORMATION_SCHEMA.COLUMNS
WHERE is_partitioning_column = 'YES'
ORDER BY table_name

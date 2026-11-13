-- Rule (BigQuery): no row of {table} sits in the __NULL__ or __UNPARTITIONED__ partition (BigQuery's equivalent of a DEFAULT partition).
SELECT partition_id, total_rows
FROM {schema}.INFORMATION_SCHEMA.PARTITIONS
WHERE table_name = '{table}' AND partition_id IN ('__NULL__', '__UNPARTITIONED__') AND total_rows > 0

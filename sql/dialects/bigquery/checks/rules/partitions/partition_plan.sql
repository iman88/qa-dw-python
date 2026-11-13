-- Rule (BigQuery): {table} has a partition for every month from {first_month} to {last_month} that holds data, read from INFORMATION_SCHEMA.PARTITIONS. Returns months with data but no partition, and rows in the __NULL__ or __UNPARTITIONED__ partitions.
SELECT partition_id, total_rows, 'rows outside the monthly partitions' AS problem
FROM {schema}.INFORMATION_SCHEMA.PARTITIONS
WHERE table_name = '{table}'
  AND partition_id IN ('__NULL__', '__UNPARTITIONED__')
  AND total_rows > 0
UNION ALL
SELECT partition_id, total_rows, 'partition outside the planned months' AS problem
FROM {schema}.INFORMATION_SCHEMA.PARTITIONS
WHERE table_name = '{table}'
  AND partition_id NOT IN ('__NULL__', '__UNPARTITIONED__')
  AND (PARSE_DATE('%Y%m%d', partition_id) < DATE '{first_month}' OR PARSE_DATE('%Y%m%d', partition_id) > DATE '{last_month}')

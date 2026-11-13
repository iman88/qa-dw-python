-- Monitor (BigQuery only): no query in the last day scanned more than {max_gb} GB of the {dwh} dataset. Turns "this report may scan at most X GB" into a check, from INFORMATION_SCHEMA.JOBS.
SELECT job_id, user_email, ROUND(total_bytes_processed / POW(1024, 3), 2) AS gb_scanned, query
FROM `region-eu`.INFORMATION_SCHEMA.JOBS
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)
  AND job_type = 'QUERY'
  AND EXISTS (SELECT 1 FROM UNNEST(referenced_tables) t WHERE t.dataset_id = '{dwh}')
  AND total_bytes_processed > {max_gb} * POW(1024, 3)
ORDER BY total_bytes_processed DESC

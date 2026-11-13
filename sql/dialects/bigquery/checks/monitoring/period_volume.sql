-- Monitor (BigQuery): in the {days} days before @as_of the {table} feed delivered at least {min_ratio} of the median of the 4 periods of {days} days before it.
WITH counts AS (
    SELECT n, (SELECT COUNT(*) FROM {raw}.{table} e
               WHERE e.ingested_at >= TIMESTAMP_SUB(@as_of, INTERVAL (n + 1) * {days} DAY)
                 AND e.ingested_at < TIMESTAMP_SUB(@as_of, INTERVAL n * {days} DAY)) AS deliveries
    FROM UNNEST(GENERATE_ARRAY(0, 4)) AS n
),
judged AS (
    SELECT (SELECT deliveries FROM counts WHERE n = 0) AS last_period,
           (SELECT APPROX_QUANTILES(deliveries, 2)[OFFSET(1)] FROM counts WHERE n > 0) AS median_before
)
SELECT last_period, median_before FROM judged WHERE last_period < {min_ratio} * median_before

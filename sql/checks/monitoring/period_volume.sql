-- Monitor: in the {days} days before :as_of the {table} feed delivered at least {min_ratio} of the median of the 4 periods of {days} days before it. Catches a lost or stalled feed without flagging a trial that is slowly winding down.
WITH periods AS (
    SELECT n,
           CAST(:as_of AS timestamptz) - (n + 1) * interval '{days} days' AS period_start,
           CAST(:as_of AS timestamptz) - n * interval '{days} days' AS period_end
    FROM generate_series(0, 4) AS n
),
counts AS (
    SELECT p.n, count(e.ingested_at) AS deliveries
    FROM periods p
    LEFT JOIN {raw}.{table} e ON e.ingested_at >= p.period_start AND e.ingested_at < p.period_end
    GROUP BY p.n
)
SELECT (SELECT deliveries FROM counts WHERE n = 0) AS last_period,
       (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY deliveries) FROM counts WHERE n > 0) AS median_before
WHERE (SELECT deliveries FROM counts WHERE n = 0)
    < {min_ratio} * (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY deliveries) FROM counts WHERE n > 0)

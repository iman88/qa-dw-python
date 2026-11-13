-- Monitor (BigQuery): the toxicity grade mix of adverse events with onset in the {days} days before @as_of has not drifted from everything before (population stability index above {max_psi} is drift).
WITH split AS (
    SELECT grade, onset_date >= DATE_SUB(DATE(@as_of), INTERVAL {days} DAY) AS recent
    FROM {dwh}.fact_adverse_event
    WHERE onset_date < DATE(@as_of) AND onset_date >= DATE '2000-01-01'
),
dist AS (
    SELECT g AS grade,
           (COUNTIF(s.recent AND s.grade = g) + 0.5) / (COUNTIF(s.recent) + 2.5) AS recent_share,
           (COUNTIF(NOT s.recent AND s.grade = g) + 0.5) / (COUNTIF(NOT s.recent) + 2.5) AS baseline_share
    FROM UNNEST(GENERATE_ARRAY(1, 5)) AS g
    CROSS JOIN split s
    GROUP BY g
)
SELECT ROUND(SUM((recent_share - baseline_share) * LN(recent_share / baseline_share)), 3) AS psi
FROM dist
HAVING psi > {max_psi}

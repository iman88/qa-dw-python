-- Monitor: the toxicity grade mix of adverse events with onset in the {days} days before :as_of has not drifted from everything before (population stability index above {max_psi} is drift).
WITH split AS (
    SELECT grade, onset_date >= CAST(:as_of AS date) - {days} AS recent
    FROM {dwh}.fact_adverse_event
    WHERE onset_date < CAST(:as_of AS date)
),
dist AS (
    SELECT g.grade,
           (count(*) FILTER (WHERE s.recent AND s.grade = g.grade) + 0.5)
             / (count(*) FILTER (WHERE s.recent) + 2.5) AS recent_share,
           (count(*) FILTER (WHERE NOT s.recent AND s.grade = g.grade) + 0.5)
             / (count(*) FILTER (WHERE NOT s.recent) + 2.5) AS baseline_share
    FROM generate_series(1, 5) AS g(grade)
    CROSS JOIN split s
    GROUP BY g.grade
),
psi AS (
    SELECT round(sum((recent_share - baseline_share) * ln(recent_share / baseline_share))::numeric, 3) AS psi
    FROM dist
)
SELECT psi FROM psi WHERE psi > {max_psi}

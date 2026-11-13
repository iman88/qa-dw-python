-- Anti-pattern: the partition column is wrapped in a function, so the planner cannot prune.
SELECT count(*) AS adverse_events
FROM {dwh}.fact_adverse_event
WHERE to_char(onset_date, 'YYYY-MM') = :year_month

-- Two copies of an existing fact, dated either side of a month boundary (the test rolls this back).
INSERT INTO {dwh}.fact_adverse_event
SELECT 'BOUNDARY-' || d.day::text, f.subject_sk, f.study_sk, f.site_sk, d.day,
       to_char(d.day, 'YYYYMMDD')::int, f.meddra_pt, f.soc, f.grade, f.is_serious, f.is_related, f.outcome,
       f.days_to_resolution, f.last_changed_at
FROM (SELECT * FROM {dwh}.fact_adverse_event ORDER BY ae_id LIMIT 1) f
CROSS JOIN (VALUES (CAST(:last_day AS date)), (CAST(:first_day AS date))) AS d(day)

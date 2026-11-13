-- Subjects with the most serious events first, then the most events.
SELECT ds.subject_id
FROM {dwh}.fact_adverse_event f
JOIN {dwh}.dim_subject ds ON ds.subject_sk = f.subject_sk
GROUP BY ds.subject_id
ORDER BY count(*) FILTER (WHERE f.is_serious) DESC, count(*) DESC, ds.subject_id
LIMIT :limit

-- Visit facts of one build, resolved to business keys.
SELECT f.visit_id, ds.subject_id, f.visit_date, f.visit_type, f.status, f.is_completed
FROM {schema}.fact_visit f
JOIN {schema}.dim_subject ds ON ds.subject_sk = f.subject_sk

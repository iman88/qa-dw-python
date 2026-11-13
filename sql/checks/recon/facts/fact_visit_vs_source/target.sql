SELECT f.visit_id, ds.subject_id, f.visit_type, d.full_date AS visit_date, f.is_completed
FROM {dwh}.fact_visit f
LEFT JOIN {dwh}.dim_subject ds ON ds.subject_sk = f.subject_sk
LEFT JOIN {dwh}.dim_date d ON d.date_key = f.visit_date_key

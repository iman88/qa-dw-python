-- The fact table, resolved back to business keys through its dimensions.
-- LEFT JOINs on purpose: an orphan fact shows up as a NULL mismatch instead of vanishing.
SELECT f.ae_id, ds.subject_id, st.study_id, f.meddra_pt, f.grade, f.is_serious,
       d.full_date AS onset_date, f.days_to_resolution
FROM {dwh}.fact_adverse_event f
LEFT JOIN {dwh}.dim_subject ds ON ds.subject_sk = f.subject_sk
LEFT JOIN {dwh}.dim_study st ON st.study_sk = f.study_sk
LEFT JOIN {dwh}.dim_date d ON d.date_key = f.onset_date_key

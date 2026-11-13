-- The same figures for :study_id, from the star schema.
SELECT (SELECT count(*) FROM {dwh}.dim_subject s WHERE s.study_id = :study_id) AS subjects,
       count(f.ae_id) AS adverse_events,
       count(f.ae_id) FILTER (WHERE f.is_serious) AS serious_adverse_events,
       count(DISTINCT f.subject_sk) AS subjects_with_events
FROM {dwh}.fact_adverse_event f
JOIN {dwh}.dim_study st ON st.study_sk = f.study_sk
WHERE st.study_id = :study_id

-- A dimension reload inserted a subject twice with a new surrogate key
INSERT INTO {dwh}.dim_subject (subject_id, study_id, site_id, arm, sex, age_at_enrolment, enrolled_date_key,
                               is_withdrawn)
SELECT subject_id, study_id, site_id, arm, sex, age_at_enrolment, enrolled_date_key, is_withdrawn
FROM {dwh}.dim_subject
ORDER BY subject_sk
LIMIT 1

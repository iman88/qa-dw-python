-- Subjects of one build by business key; surrogate keys differ between builds.
SELECT subject_id, study_id, site_id, arm, sex, age_at_enrolment, enrolled_date_key, is_withdrawn
FROM {schema}.dim_subject

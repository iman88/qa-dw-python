-- dim_subject holds one row per source subject, with derived age at enrolment and withdrawal flag
-- Source side of the comparison.
SELECT subject_id, study_id, site_id, arm, sex,
       extract(YEAR FROM enrolled_on)::int - birth_year AS age_at_enrolment,
       withdrawn_on IS NOT NULL AS is_withdrawn
FROM {src}.subject

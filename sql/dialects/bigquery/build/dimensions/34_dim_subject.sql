-- BigQuery: subject dimension with derived age and withdrawal flag.
CREATE OR REPLACE TABLE {dwh}.dim_subject
CLUSTER BY subject_id AS
SELECT ROW_NUMBER() OVER (ORDER BY subject_id) AS subject_sk,
       subject_id, study_id, site_id, arm, sex,
       EXTRACT(YEAR FROM enrolled_on) - birth_year AS age_at_enrolment,
       CAST(FORMAT_DATE('%Y%m%d', enrolled_on) AS INT64) AS enrolled_date_key,
       withdrawn_on IS NOT NULL AS is_withdrawn
FROM {latest}.subject;

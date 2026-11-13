-- BigQuery: visit fact, partitioned by visit month, clustered by study and subject, partition filter required.
CREATE OR REPLACE TABLE {dwh}.fact_visit
PARTITION BY DATE_TRUNC(visit_date, MONTH)
CLUSTER BY study_sk, subject_sk
OPTIONS (require_partition_filter = TRUE) AS
SELECT v.visit_id, ds.subject_sk, dst.study_sk, v.visit_date,
       CAST(FORMAT_DATE('%Y%m%d', v.visit_date) AS INT64) AS visit_date_key,
       v.visit_type, v.status, v.status = 'COMPLETED' AS is_completed
FROM {latest}.visit v
JOIN {dwh}.dim_subject ds ON ds.subject_id = v.subject_id
JOIN {dwh}.dim_study dst ON dst.study_id = ds.study_id;

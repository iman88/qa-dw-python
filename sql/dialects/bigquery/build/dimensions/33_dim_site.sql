-- BigQuery: site dimension, type 2, one row per version; keys from ROW_NUMBER over (site_id, valid_from).
CREATE OR REPLACE TABLE {dwh}.dim_site
CLUSTER BY site_id AS
SELECT ROW_NUMBER() OVER (ORDER BY site_id, valid_from) AS site_sk,
       site_id, study_id, country_code, investigator, status, valid_from, valid_to, is_current
FROM {hist}.site_history
WHERE NOT is_deleted;

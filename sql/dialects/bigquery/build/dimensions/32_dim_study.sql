-- BigQuery: study dimension. There are no serial columns; surrogate keys come from ROW_NUMBER over the business key, so a rebuild gives the same keys.
CREATE
OR REPLACE TABLE {dwh}.dim_study AS
SELECT ROW_NUMBER()                                        OVER (ORDER BY study_id) AS study_sk, study_id,
       study_code,
       phase,
       therapeutic_area,
       CAST(FORMAT_DATE('%Y%m%d', start_date) AS INT64) AS start_date_key
FROM {latest}.study;

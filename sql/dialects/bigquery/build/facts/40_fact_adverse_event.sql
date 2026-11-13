-- BigQuery: adverse event fact, partitioned by onset month, clustered by study and subject, partition filter required. The site version is the one valid at 00:00 UTC on the onset date, as in Postgres.
CREATE OR REPLACE TABLE {dwh}.fact_adverse_event
PARTITION BY DATE_TRUNC(onset_date, MONTH)
CLUSTER BY study_sk, subject_sk
OPTIONS (require_partition_filter = TRUE) AS
SELECT ae.ae_id, ds.subject_sk, dst.study_sk, dsi.site_sk, ae.onset_date,
       CAST(FORMAT_DATE('%Y%m%d', ae.onset_date) AS INT64) AS onset_date_key,
       ae.meddra_pt, ae.soc, ae.grade, ae.serious AS is_serious, ae.related AS is_related, ae.outcome,
       DATE_DIFF(ae.resolved_date, ae.onset_date, DAY) AS days_to_resolution,
       ae.last_changed_at
FROM {latest}.adverse_event ae
JOIN {dwh}.dim_subject ds ON ds.subject_id = ae.subject_id
JOIN {dwh}.dim_study dst ON dst.study_id = ds.study_id
JOIN {dwh}.dim_site dsi
  ON dsi.site_id = ds.site_id
 AND TIMESTAMP(ae.onset_date) >= dsi.valid_from
 AND TIMESTAMP(ae.onset_date) < dsi.valid_to;

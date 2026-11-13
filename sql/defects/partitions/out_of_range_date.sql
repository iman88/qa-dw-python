-- A date parsed with day and month swapped landed outside the partition plan
INSERT INTO {dwh}.fact_adverse_event
SELECT ae_id || '-X', subject_sk, study_sk, site_sk, date '2031-01-05', 20310105, meddra_pt, soc,
       grade, is_serious, is_related, outcome, days_to_resolution, last_changed_at
FROM {dwh}.fact_adverse_event
ORDER BY ae_id
LIMIT 1

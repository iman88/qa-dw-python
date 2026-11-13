-- Every subject with adverse events and their records, as the narrative service receives them: the evaluation set.
SELECT subject_id, ae_id, meddra_pt, grade, is_serious, onset_date::text AS onset_date, outcome
FROM {dwh}.v_adverse_event_detail
ORDER BY subject_id, onset_date, ae_id

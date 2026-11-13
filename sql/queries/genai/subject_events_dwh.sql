-- The records the narrative service receives for one subject, read from the warehouse.
SELECT ae_id, meddra_pt, grade, is_serious, onset_date::text AS onset_date, outcome
FROM {dwh}.v_adverse_event_detail
WHERE subject_id = :subject_id
ORDER BY onset_date, ae_id

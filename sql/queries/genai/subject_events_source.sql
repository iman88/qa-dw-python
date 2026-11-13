-- The same subject's adverse events from the source system, to evaluate the narrative against.
SELECT ae_id, meddra_pt, grade, serious AS is_serious
FROM {src}.adverse_event
WHERE subject_id = :subject_id

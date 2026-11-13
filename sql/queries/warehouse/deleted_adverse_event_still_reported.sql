-- Adverse events deleted in the source system that the warehouse still reports (should be none).
SELECT d.ae_id, d.subject_id, d.onset_date
FROM {dwh}.v_adverse_event_detail d
WHERE d.ae_id IN (SELECT e.ae_id FROM {raw}.adverse_event_events e WHERE e.op = 'D')

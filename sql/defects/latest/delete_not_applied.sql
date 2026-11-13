-- A delete event was ignored, so a record entered in error is still reported
INSERT INTO {latest}.adverse_event
SELECT ae_id, subject_id, meddra_pt, soc, grade, serious, related, onset_date, resolved_date, outcome,
       change_seq, valid_from
FROM {hist}.adverse_event_history
WHERE is_current AND is_deleted
ORDER BY ae_id
LIMIT 1

-- Deleted adverse events whose current history row is not a tombstone (should be none).
SELECT DISTINCT r.ae_id
FROM {raw}.adverse_event_events r
WHERE r.op = 'D'
  AND NOT EXISTS (SELECT 1 FROM {hist}.adverse_event_history h
                  WHERE h.ae_id = r.ae_id AND h.is_current AND h.is_deleted)

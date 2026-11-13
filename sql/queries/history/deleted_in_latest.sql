-- Deleted adverse events that still appear in the latest layer (should be none).
SELECT count(*)
FROM {latest}.adverse_event l
WHERE l.ae_id IN (SELECT e.ae_id FROM {raw}.adverse_event_events e WHERE e.op = 'D')

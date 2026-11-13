-- An inner join on a stale dimension silently dropped facts
DELETE FROM {dwh}.fact_adverse_event
WHERE ae_id IN (SELECT ae_id FROM {dwh}.fact_adverse_event ORDER BY ae_id LIMIT 3)

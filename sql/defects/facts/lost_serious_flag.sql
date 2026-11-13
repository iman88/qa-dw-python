-- A boolean cast turned some serious events into non-serious ones
UPDATE {dwh}.fact_adverse_event
SET is_serious = false
WHERE ae_id IN (SELECT ae_id FROM {dwh}.fact_adverse_event WHERE is_serious ORDER BY ae_id LIMIT 2)

-- A mapping table shifted toxicity grades by one
UPDATE {dwh}.fact_adverse_event
SET grade = grade + 1
WHERE ae_id IN (SELECT ae_id FROM {dwh}.fact_adverse_event WHERE grade < 5 ORDER BY ae_id LIMIT 2)

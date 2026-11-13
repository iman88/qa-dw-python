-- A reporter's e-mail address was typed into the event description and copied into the warehouse
UPDATE {dwh}.fact_adverse_event
SET meddra_pt = meddra_pt || ' (reported by dr.ionescu@example.org)'
WHERE ae_id = (SELECT min(ae_id) FROM {dwh}.fact_adverse_event)

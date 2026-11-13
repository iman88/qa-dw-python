-- A fact row was loaded before its dimension row existed (late-arriving dimension)
UPDATE {dwh}.fact_adverse_event
SET subject_sk = -1
WHERE ae_id = (SELECT min (ae_id) FROM {dwh}.fact_adverse_event)

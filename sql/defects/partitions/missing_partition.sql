-- A maintenance job detached a monthly partition and never re-attached it
ALTER TABLE {dwh}.fact_adverse_event DETACH PARTITION {dwh}.fact_adverse_event_202509

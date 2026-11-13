-- What the incremental batch contains: adverse event events that arrived from :batch_start, by kind.
-- changes_to_earlier_records counts updates and deletes of records first loaded before the batch:
-- the cases an incremental load must merge into existing rows rather than append.
SELECT count(*) AS events,
       count(*) FILTER (WHERE r.op = 'D') AS deletes,
       count(*) - count(DISTINCT r.change_seq) AS redelivered,
       count(*) FILTER (WHERE r.op <> 'I' AND EXISTS (
           SELECT 1 FROM {raw}.adverse_event_events e
           WHERE e.ae_id = r.ae_id AND e.ingested_at < CAST(:batch_start AS timestamptz))) AS changes_to_earlier_records
FROM {raw}.adverse_event_events r
WHERE r.ingested_at >= CAST(:batch_start AS timestamptz)

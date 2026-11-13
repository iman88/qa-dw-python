-- Nine out of ten adverse event batches of the last four weeks never arrived (a lossy transfer).
DELETE FROM {raw}.adverse_event_events
WHERE ingested_at >= timestamptz '2026-06-02 23:59+00' AND change_seq % 10 <> 0

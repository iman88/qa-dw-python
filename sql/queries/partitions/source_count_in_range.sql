-- Adverse events with onset in [:date_from, :date_until), from the source system.
SELECT count(*) AS adverse_events
FROM {src}.adverse_event
WHERE onset_date >= CAST(:date_from AS date)
  AND onset_date < CAST(:date_until AS date)

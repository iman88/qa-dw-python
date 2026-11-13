-- Adverse events with onset in [:date_from, :date_until). A plain range on the partition key, so it prunes.
SELECT count(*) AS adverse_events
FROM {dwh}.fact_adverse_event
WHERE onset_date >= CAST(:date_from AS date)
  AND onset_date < CAST(:date_until AS date)

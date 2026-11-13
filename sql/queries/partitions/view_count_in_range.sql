-- The same date filter applied through the reporting view.
SELECT count(*) AS adverse_events
FROM {dwh}.v_adverse_event_detail
WHERE onset_date >= CAST(:date_from AS date)
  AND onset_date < CAST(:date_until AS date)

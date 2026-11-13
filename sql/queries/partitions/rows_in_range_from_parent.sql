-- The same rows read through the parent table with a date filter.
SELECT ae_id, grade, is_serious
FROM {dwh}.fact_adverse_event
WHERE onset_date >= CAST(:date_from AS date)
  AND onset_date < CAST(:date_until AS date)

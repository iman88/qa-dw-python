SELECT onset_date, tableoid::regclass::text AS partition_name
FROM {dwh}.fact_adverse_event
WHERE ae_id LIKE 'BOUNDARY-%'
ORDER BY onset_date

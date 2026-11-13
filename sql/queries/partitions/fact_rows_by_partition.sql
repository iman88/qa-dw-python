-- Rows per physical partition of fact_adverse_event, with the onset month they hold.
SELECT tableoid::regclass::text AS partition_name, to_char(onset_date, 'YYYYMM') AS month, count(*) AS rows
FROM {dwh}.fact_adverse_event
GROUP BY 1, 2

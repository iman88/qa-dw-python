-- Partition key of every partitioned table in one schema, for example "RANGE (onset_date)".

SELECT cl.relname AS object_name, pg_get_partkeydef(cl.oid) AS partition_key
FROM pg_class cl
JOIN pg_namespace n ON n.oid = cl.relnamespace
WHERE n.nspname = :schema_name AND cl.relkind = 'p'
ORDER BY cl.relname

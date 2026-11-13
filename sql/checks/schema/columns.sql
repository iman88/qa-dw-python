-- Every table, partitioned table and view in one schema, with its columns in order.
-- Partitions themselves are left out: they inherit the parent's columns.

SELECT cl.relname AS object_name,
       CASE cl.relkind WHEN 'r' THEN 'table' WHEN 'p' THEN 'partitioned table' WHEN 'v' THEN 'view' END
           AS object_type,
       a.attname AS column_name,
       format_type(a.atttypid, a.atttypmod) AS data_type,
       a.attnotnull AS not_null
FROM pg_class cl
JOIN pg_namespace n ON n.oid = cl.relnamespace
JOIN pg_attribute a ON a.attrelid = cl.oid AND a.attnum > 0 AND NOT a.attisdropped
WHERE n.nspname = :schema_name
  AND cl.relkind IN ('r', 'p', 'v')
  AND NOT cl.relispartition
ORDER BY cl.relname, a.attnum

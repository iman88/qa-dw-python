-- Every table of a schema (partitioned parents, not their partitions), to checksum a whole build.
SELECT c.relname AS table_name
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = :schema_name AND c.relkind IN ('r', 'p') AND NOT c.relispartition
ORDER BY c.relname

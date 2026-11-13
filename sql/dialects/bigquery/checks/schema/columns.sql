-- BigQuery: every table and view in one dataset with its columns in order, for the schema contracts.
SELECT c.table_name AS object_name,
       CASE t.table_type WHEN 'VIEW' THEN 'view' ELSE 'table' END AS object_type,
       c.column_name,
       c.data_type,
       c.is_nullable = 'NO' AS not_null
FROM {schema}.INFORMATION_SCHEMA.COLUMNS c
JOIN {schema}.INFORMATION_SCHEMA.TABLES t USING (table_name)
ORDER BY c.table_name, c.ordinal_position

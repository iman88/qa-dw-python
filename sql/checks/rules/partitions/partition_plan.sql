-- Rule: {table} has one partition per month from {first_month} to {last_month}, each exactly one
-- calendar month wide, named <table>_YYYYMM after its lower bound, plus a DEFAULT partition.
-- Returns one row per problem found in the catalog.

WITH parts AS (
    SELECT c.relname AS partition_name,
           pg_get_expr(c.relpartbound, c.oid) AS bound
    FROM pg_inherits i
    JOIN pg_class c ON c.oid = i.inhrelid
    JOIN pg_class p ON p.oid = i.inhparent
    JOIN pg_namespace n ON n.oid = p.relnamespace
    WHERE n.nspname = '{schema}' AND p.relname = '{table}'
),
ranges AS (
    SELECT partition_name,
           substring(bound FROM 'FROM \(''([^'']+)''\)')::date AS lower_bound,
           substring(bound FROM 'TO \(''([^'']+)''\)')::date   AS upper_bound
    FROM parts
    WHERE bound <> 'DEFAULT'
),
expected AS (
    SELECT m::date AS month
    FROM generate_series(date '{first_month}', date '{last_month}', interval '1 month') AS m
)
SELECT e.month AS month, NULL::text AS partition_name, 'missing partition' AS problem
FROM expected e
LEFT JOIN ranges r ON r.lower_bound = e.month
WHERE r.partition_name IS NULL
UNION ALL
SELECT r.lower_bound, r.partition_name, 'not exactly one calendar month'
FROM ranges r
WHERE extract(DAY FROM r.lower_bound) <> 1
   OR r.upper_bound <> (r.lower_bound + interval '1 month')::date
UNION ALL
SELECT r.lower_bound, r.partition_name, 'name does not match its bounds'
FROM ranges r
WHERE r.partition_name <> '{table}_' || to_char(r.lower_bound, 'YYYYMM')
UNION ALL
SELECT NULL, NULL, 'no DEFAULT partition'
WHERE NOT EXISTS (SELECT 1 FROM parts WHERE bound = 'DEFAULT')

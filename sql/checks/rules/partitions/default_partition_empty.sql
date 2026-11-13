-- Rule: no row of {table} falls outside the planned monthly partitions.
-- Anything in the DEFAULT partition has a date nobody planned for (bad parse, wrong year...).

SELECT *
FROM {schema}.{table}_default

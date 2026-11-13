-- Rule: mandatory columns of {table} are always filled.
-- {condition} is "col_a IS NULL OR col_b IS NULL ...", built from the column list.

SELECT *
FROM {schema}.{table}
WHERE {condition}

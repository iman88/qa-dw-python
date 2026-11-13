-- Rule: ({columns}) identifies exactly one row in {table}.
-- Returns every key that appears more than once, with the number of copies.

SELECT {columns}, count(*) AS copies
FROM {schema}.{table}
GROUP BY {columns}
HAVING count(*) > 1

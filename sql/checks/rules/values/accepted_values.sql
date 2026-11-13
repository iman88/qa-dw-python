-- Rule: {table}.{column} only holds values from the agreed list.

SELECT {column}, count(*) AS rows_with_value
FROM {schema}.{table}
WHERE {column} IS NULL OR {column} NOT IN ({values})
GROUP BY {column}

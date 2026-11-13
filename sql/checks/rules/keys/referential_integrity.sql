-- Rule: every {fact}.{fk} has a matching row in {dim}.{pk}.
-- Warehouses rarely enforce foreign keys, so orphans are found by query.

SELECT f.{fk}, count(*) AS orphan_rows
FROM {schema}.{fact} f
LEFT JOIN {schema}.{dim} d ON d.{pk} = f.{fk}
WHERE d.{pk} IS NULL
GROUP BY f.{fk}

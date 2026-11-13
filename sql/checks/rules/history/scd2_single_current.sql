-- Rule: exactly one current version per {key} in {table}, and it is the open-ended one.

SELECT {key},
       count(*) FILTER (WHERE is_current) AS current_versions,
       max(valid_to) AS last_valid_to
FROM {schema}.{table}
GROUP BY {key}
HAVING count(*) FILTER (WHERE is_current) <> 1
    OR bool_or(is_current AND valid_to <> timestamptz '9999-12-31 00:00:00+00')

-- Rule: the versions of one {key} in {table} form a clean timeline.
-- Each version must end exactly where the next one starts: no overlap and no gap. A version may be
-- empty (valid_from = valid_to) when two changes carry the same timestamp; it never ends before it
-- starts. Ties are ordered by valid_to, so an empty version sorts before the one that replaced it.

SELECT {key}, valid_from, valid_to, next_valid_from
FROM (
    SELECT {key}, valid_from, valid_to,
           LEAD(valid_from) OVER (PARTITION BY {key} ORDER BY valid_from, valid_to) AS next_valid_from
    FROM {schema}.{table}
) versions
WHERE valid_from > valid_to
   OR (next_valid_from IS NOT NULL AND valid_to <> next_valid_from)

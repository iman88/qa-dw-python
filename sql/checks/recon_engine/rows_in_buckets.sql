-- The rows of the buckets whose checksums differ (:buckets), fetched for the column-by-column comparison.
SELECT q.*
FROM ({query}) AS q
WHERE mod(abs(hashtextextended(concat_ws('|', {key_expr}), 0)), {buckets}) = ANY(:buckets)

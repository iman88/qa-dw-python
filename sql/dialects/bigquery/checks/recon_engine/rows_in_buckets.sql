-- BigQuery: the rows of the buckets whose checksums differ (@buckets), fetched for the column-by-column comparison.
SELECT q.*
FROM ({query}) AS q
WHERE MOD(ABS(FARM_FINGERPRINT(CONCAT({key_expr}))), {buckets}) IN UNNEST(@buckets)

-- BigQuery: checksum per bucket with FARM_FINGERPRINT and BIT_XOR: rows are spread over {buckets} buckets by a fingerprint of their key; each bucket gets a row count and an order-independent XOR of row fingerprints.
SELECT MOD(ABS(FARM_FINGERPRINT(CONCAT({key_expr}))), {buckets}) AS bucket,
       COUNT(*)                                                  AS row_count,
       BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(q)))              AS row_hash_sum
FROM ({query}) AS q
GROUP BY bucket

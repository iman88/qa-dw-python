-- Checksum per bucket: rows are spread over {buckets} buckets by a hash of their key; each bucket gets a row count and an order-independent sum of row hashes. Only buckets that differ between source and target are fetched.
SELECT mod(abs(hashtextextended(concat_ws('|', {key_expr}), 0)), {buckets}) AS bucket,
       count(*) AS row_count,
       sum(hashtextextended(concat_ws('|', {row_expr}), 0)::numeric) AS row_hash_sum
FROM ({query}) AS q
GROUP BY 1

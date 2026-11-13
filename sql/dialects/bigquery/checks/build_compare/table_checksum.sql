-- BigQuery: row count and order-independent checksum of a whole table, to prove a re-run changed nothing.
SELECT COUNT(*) AS row_count, BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(t))) AS checksum
FROM {schema}.{table} AS t

-- Row count and order-independent checksum of a whole table, to prove a re-run changed nothing.
SELECT count(*) AS row_count, coalesce(sum(hashtextextended(t::text, 0)::numeric), 0) AS checksum
FROM {schema}.{table} AS t

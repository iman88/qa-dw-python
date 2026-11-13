-- hist.{history_table} of one build, for comparing two builds of the same data.
SELECT {columns}, change_seq, op, valid_from, valid_to, is_current, is_deleted, first_ingested_at
FROM {schema}.{history_table}

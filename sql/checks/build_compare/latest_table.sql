-- latest.{entity} of one build, for comparing two builds of the same data.
SELECT {columns}, last_change_seq, last_changed_at
FROM {schema}.{entity}

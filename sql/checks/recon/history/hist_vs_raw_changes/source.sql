-- Every distinct change of {entity} delivered to raw is kept exactly once in hist.{history_table}
-- Source side of the comparison.
SELECT DISTINCT change_seq, op, changed_at
FROM {raw}.{events_table}

-- Every change of {entity} kept in history.
SELECT change_seq, op, valid_from AS changed_at
FROM {hist}.{history_table}

-- Rule: a {entity} whose last change was a delete is absent from the latest layer.

SELECT l.{key}, h.change_seq AS delete_change_seq, h.valid_from AS deleted_at
FROM {latest}.{entity} l
JOIN {hist}.{history_table} h
  ON h.{key} = l.{key}
 AND h.is_current
 AND h.is_deleted

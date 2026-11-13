-- Dedup ordered by ingestion time instead of change_seq, so an older version won
UPDATE {latest}.adverse_event l
SET grade = h.grade
FROM {hist}.adverse_event_history h
WHERE h.ae_id = l.ae_id
  AND NOT h.is_current
  AND h.grade <> l.grade
  AND h.change_seq = (SELECT min(change_seq) FROM {hist}.adverse_event_history x
                      WHERE x.ae_id = h.ae_id AND x.grade <> l.grade)

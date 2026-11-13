-- Current-state view over history for one entity ({entity}).
-- The latest layer derives the same thing from raw with a different method;
-- reconciling the two proves both are right.

CREATE VIEW {hist}.v_{entity}_current AS
SELECT {columns}, change_seq AS last_change_seq, valid_from AS last_changed_at
FROM {hist}.{history_table}
WHERE is_current AND NOT is_deleted;

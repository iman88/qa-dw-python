-- The latest job appended a redelivered event instead of collapsing it
INSERT INTO {latest}.adverse_event
SELECT * FROM {latest}.adverse_event ORDER BY ae_id LIMIT 1

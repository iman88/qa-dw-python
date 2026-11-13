-- An SCD2 job forgot to close the previous version before opening the next
UPDATE {hist}.site_history
SET valid_to = valid_to + interval '10 days'
WHERE change_seq = (SELECT min(change_seq) FROM {hist}.site_history WHERE NOT is_current)

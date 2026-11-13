-- The stored results of one monitoring run.
SELECT check_id, kind, passed, offending_rows
FROM qa_monitor.check_results
WHERE run_id = :run_id
ORDER BY kind, check_id

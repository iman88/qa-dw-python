-- The most recent earlier run on the same evaluation set and engine, per metric, to compare against.
WITH previous AS (
    SELECT run_id FROM qa_monitor.genai_eval_runs
    WHERE evalset_version = :evalset_version AND engine = :engine AND run_id <> :run_id
    GROUP BY run_id ORDER BY max(ran_at) DESC LIMIT 1
)
SELECT metric, passed, total, prompt_version, model
FROM qa_monitor.genai_eval_runs
WHERE run_id = (SELECT p.run_id FROM previous p)

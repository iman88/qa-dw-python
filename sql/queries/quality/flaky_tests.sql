-- Flaky tests: tests that both passed and failed over the last :runs recorded runs, most unstable first.
WITH recent AS (
    SELECT run_id FROM qa_monitor.test_results GROUP BY run_id ORDER BY max(ran_at) DESC LIMIT :runs
)
SELECT test_id,
       count(*) FILTER (WHERE outcome = 'passed') AS passed,
       count(*) FILTER (WHERE outcome = 'failed') AS failed,
       round(100.0 * count(*) FILTER (WHERE outcome = 'failed') / count(*), 1) AS failure_rate_pct
FROM qa_monitor.test_results
WHERE run_id IN (SELECT r.run_id FROM recent r)
GROUP BY test_id
HAVING count(*) FILTER (WHERE outcome = 'passed') > 0 AND count(*) FILTER (WHERE outcome = 'failed') > 0
ORDER BY failure_rate_pct DESC, test_id

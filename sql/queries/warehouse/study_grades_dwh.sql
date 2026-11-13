-- Adverse events per grade for :study_id, from the reporting view.
SELECT grade, count(*) AS events
FROM {dwh}.v_adverse_event_detail
WHERE study_id = :study_id
GROUP BY grade
ORDER BY grade

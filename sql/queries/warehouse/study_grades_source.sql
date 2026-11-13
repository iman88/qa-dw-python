-- Adverse events per grade for :study_id, from the source system.
SELECT ae.grade, count(*) AS events
FROM {src}.adverse_event ae
JOIN {src}.subject su USING (subject_id)
WHERE su.study_id = :study_id
GROUP BY ae.grade
ORDER BY ae.grade

-- Aggregate: adverse events, serious adverse events and grade sum per study
-- Source side of the comparison.
SELECT su.study_id,
       count(*) AS adverse_events,
       count(*) FILTER (WHERE ae.serious) AS serious_adverse_events,
       sum(ae.grade) AS grade_sum
FROM {src}.adverse_event ae
JOIN {src}.subject su USING (subject_id)
GROUP BY su.study_id

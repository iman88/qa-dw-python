-- Reporting view v_safety_by_study_month equals safety totals per study and month computed from the source system
-- Source side of the comparison.
SELECT su.study_id,
       to_char(ae.onset_date, 'YYYY-MM') AS year_month,
       count(*) AS adverse_events,
       count(*) FILTER (WHERE ae.serious) AS serious_adverse_events,
       count(DISTINCT ae.subject_id) AS subjects_with_events,
       max(ae.grade) AS max_grade
FROM {src}.adverse_event ae
JOIN {src}.subject su USING (subject_id)
GROUP BY 1, 2

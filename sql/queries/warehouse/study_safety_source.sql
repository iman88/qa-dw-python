-- Headline safety figures for :study_id, from the source system.
SELECT (SELECT count(*) FROM {src}.subject s WHERE s.study_id = :study_id) AS subjects,
       count(ae.ae_id) AS adverse_events,
       count(ae.ae_id) FILTER (WHERE ae.serious) AS serious_adverse_events,
       count(DISTINCT ae.subject_id) AS subjects_with_events
FROM {src}.adverse_event ae
JOIN {src}.subject su USING (subject_id)
WHERE su.study_id = :study_id

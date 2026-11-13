-- Every current adverse event reaches fact_adverse_event with the right subject, study, term, grade, seriousness, onset date and duration
-- Source side of the comparison.
SELECT ae.ae_id, ae.subject_id, su.study_id, ae.meddra_pt, ae.grade,
       ae.serious AS is_serious, ae.onset_date,
       ae.resolved_date - ae.onset_date AS days_to_resolution
FROM {src}.adverse_event ae
JOIN {src}.subject su USING (subject_id)

-- Reporting view v_adverse_event_detail shows every adverse event with the right study, subject, site and clinical attributes
-- Source side of the comparison.
SELECT ae.ae_id, su.study_id, st.study_code, ae.subject_id, su.arm, su.site_id, ae.onset_date,
       to_char(ae.onset_date, 'YYYY-MM') AS year_month, ae.meddra_pt, ae.soc, ae.grade,
       ae.serious AS is_serious, ae.related AS is_related, ae.outcome,
       ae.resolved_date - ae.onset_date AS days_to_resolution
FROM {src}.adverse_event ae
JOIN {src}.subject su USING (subject_id)
JOIN {src}.study st ON st.study_id = su.study_id

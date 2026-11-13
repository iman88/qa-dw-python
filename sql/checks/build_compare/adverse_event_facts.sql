-- Adverse event facts of one build, resolved to business keys (including the site version valid at onset).
SELECT ae_id, study_id, subject_id, site_id, investigator_at_onset, onset_date, meddra_pt, grade, is_serious,
       is_related, outcome, days_to_resolution
FROM {schema}.v_adverse_event_detail

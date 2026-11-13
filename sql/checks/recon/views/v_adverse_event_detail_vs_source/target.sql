SELECT ae_id, study_id, study_code, subject_id, arm, site_id, onset_date, year_month, meddra_pt, soc,
       grade, is_serious, is_related, outcome, days_to_resolution
FROM {dwh}.v_adverse_event_detail

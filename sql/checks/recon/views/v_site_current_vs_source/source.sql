-- View v_site_current equals the sites the source system holds today
-- Source side of the comparison.
SELECT site_id, study_id, country_code, investigator, status
FROM {src}.site

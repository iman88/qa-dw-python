-- Current version of every site, for consumers that do not care about history.

CREATE VIEW {dwh}.v_site_current AS
SELECT site_sk, site_id, study_id, country_code, investigator, status, valid_from AS current_since
FROM {dwh}.dim_site
WHERE is_current;

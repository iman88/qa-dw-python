-- Site versions of one build by business key (site_id, valid_from); surrogate keys differ between builds.
SELECT site_id, valid_from, valid_to, is_current, study_id, country_code, investigator, status
FROM {schema}.dim_site

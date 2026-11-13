-- Facts were joined to the current site version instead of the version valid at onset
UPDATE {dwh}.fact_adverse_event f
SET site_sk = cur.site_sk
FROM {dwh}.dim_site old
JOIN {dwh}.dim_site cur ON cur.site_id = old.site_id AND cur.is_current
WHERE f.site_sk = old.site_sk AND NOT old.is_current

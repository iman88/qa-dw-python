-- The is_current flag was not reset when a newer site version arrived
UPDATE {dwh}.dim_site
SET is_current = true
WHERE site_sk = (SELECT min(site_sk) FROM {dwh}.dim_site WHERE NOT is_current)

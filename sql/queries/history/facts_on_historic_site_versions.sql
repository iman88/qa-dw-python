-- Adverse events linked to a site version that is no longer current.
SELECT count(*)
FROM {dwh}.fact_adverse_event f
JOIN {dwh}.dim_site s ON s.site_sk = f.site_sk
WHERE NOT s.is_current

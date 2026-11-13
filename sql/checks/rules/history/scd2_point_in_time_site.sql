-- Rule: each adverse event points at the site version that was valid at 00:00 UTC on its
-- onset date, not simply at the current version of the site.

SELECT f.ae_id,
       f.onset_date,
       f.site_sk        AS loaded_site_sk,
       expected.site_sk AS expected_site_sk
FROM {dwh}.fact_adverse_event f
JOIN {dwh}.dim_subject ds ON ds.subject_sk = f.subject_sk
LEFT JOIN {dwh}.dim_site expected
       ON expected.site_id = ds.site_id
      AND f.onset_date::timestamptz >= expected.valid_from
      AND f.onset_date::timestamptz < expected.valid_to
WHERE expected.site_sk IS DISTINCT FROM f.site_sk

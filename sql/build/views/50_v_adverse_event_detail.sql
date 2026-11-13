-- Reporting view: one row per adverse event with its dimensions flattened, as analysts query it.
-- The site columns come from the version valid at onset (via site_sk), not the current site.
-- Filters on onset_date still prune the fact partitions underneath.

CREATE VIEW {dwh}.v_adverse_event_detail AS
SELECT f.ae_id,
       st.study_id,
       st.study_code,
       ds.subject_id,
       ds.arm,
       si.site_id,
       si.country_code,
       si.investigator AS investigator_at_onset,
       f.onset_date,
       d.year_month,
       f.meddra_pt,
       f.soc,
       f.grade,
       f.is_serious,
       f.is_related,
       f.outcome,
       f.days_to_resolution
FROM {dwh}.fact_adverse_event f
JOIN {dwh}.dim_study st ON st.study_sk = f.study_sk
JOIN {dwh}.dim_subject ds ON ds.subject_sk = f.subject_sk
JOIN {dwh}.dim_site si ON si.site_sk = f.site_sk
JOIN {dwh}.dim_date d ON d.date_key = f.onset_date_key;

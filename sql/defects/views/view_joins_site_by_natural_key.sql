-- The monthly safety view joined the SCD2 site dimension on site_id instead of site_sk, fanning out rows
CREATE OR REPLACE VIEW {dwh}.v_safety_by_study_month AS
SELECT st.study_id,
       to_char(f.onset_date, 'YYYY-MM')                AS year_month,
       count(*)                                        AS adverse_events,
       count(*) FILTER (WHERE f.is_serious)            AS serious_adverse_events,
       count(DISTINCT f.subject_sk)                    AS subjects_with_events,
       max(f.grade)                                    AS max_grade
FROM {dwh}.fact_adverse_event f
JOIN {dwh}.dim_study st ON st.study_sk = f.study_sk
JOIN {dwh}.dim_site cur ON cur.site_sk = f.site_sk
JOIN {dwh}.dim_site si ON si.site_id = cur.site_id
GROUP BY st.study_id, to_char(f.onset_date, 'YYYY-MM')

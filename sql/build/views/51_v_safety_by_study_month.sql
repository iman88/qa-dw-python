-- Reporting view: safety totals per study and onset month.

CREATE VIEW {dwh}.v_safety_by_study_month AS
SELECT st.study_id,
       to_char(f.onset_date, 'YYYY-MM')                AS year_month,
       count(*)                                        AS adverse_events,
       count(*) FILTER (WHERE f.is_serious)            AS serious_adverse_events,
       count(DISTINCT f.subject_sk)                    AS subjects_with_events,
       max(f.grade)                                    AS max_grade
FROM {dwh}.fact_adverse_event f
JOIN {dwh}.dim_study st ON st.study_sk = f.study_sk
GROUP BY st.study_id, to_char(f.onset_date, 'YYYY-MM');

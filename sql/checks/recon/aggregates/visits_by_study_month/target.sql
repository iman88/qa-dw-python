SELECT st.study_id,
       d.year_month,
       count(*) FILTER (WHERE f.is_completed) AS completed_visits
FROM {dwh}.fact_visit f
JOIN {dwh}.dim_study st ON st.study_sk = f.study_sk
JOIN {dwh}.dim_date d ON d.date_key = f.visit_date_key
GROUP BY 1, 2

SELECT st.study_id,
       count(*) AS adverse_events,
       count(*) FILTER (WHERE f.is_serious) AS serious_adverse_events,
       sum(f.grade) AS grade_sum
FROM {dwh}.fact_adverse_event f
JOIN {dwh}.dim_study st ON st.study_sk = f.study_sk
GROUP BY st.study_id

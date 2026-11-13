-- Aggregate: completed visits per study and month
-- Source side of the comparison.
SELECT su.study_id,
       to_char(v.visit_date, 'YYYY-MM') AS year_month,
       count(*) FILTER (WHERE v.status = 'COMPLETED') AS completed_visits
FROM {src}.visit v
JOIN {src}.subject su USING (subject_id)
GROUP BY 1, 2

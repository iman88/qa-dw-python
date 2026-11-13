-- Every visit reaches fact_visit with the right subject, date and completion flag
-- Source side of the comparison.
SELECT visit_id, subject_id, visit_type, visit_date, status = 'COMPLETED' AS is_completed
FROM {src}.visit

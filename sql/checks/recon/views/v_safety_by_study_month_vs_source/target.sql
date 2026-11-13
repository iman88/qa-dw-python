SELECT study_id, year_month, adverse_events, serious_adverse_events, subjects_with_events, max_grade
FROM {dwh}.v_safety_by_study_month

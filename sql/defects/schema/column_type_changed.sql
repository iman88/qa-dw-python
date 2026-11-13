-- A migration changed a numeric column to text, which breaks sorting and aggregation downstream
ALTER TABLE {dwh}.dim_subject ALTER COLUMN age_at_enrolment TYPE text

-- The enrolment date key is widened from integer to bigint: every existing value still fits.
ALTER TABLE {dwh}.dim_subject ALTER COLUMN enrolled_date_key TYPE bigint

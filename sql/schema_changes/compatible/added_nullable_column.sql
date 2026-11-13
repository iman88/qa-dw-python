-- A new optional attribute is added to the subject dimension: existing queries keep working.
ALTER TABLE {dwh}.dim_subject ADD COLUMN ethnicity_code text

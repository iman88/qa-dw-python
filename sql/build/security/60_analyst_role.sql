-- Column-level access for analysts: they read the reporting views, never the raw, history or latest layers, and never the investigator's name.
-- Roles are cluster-wide, so the role is created once and reused (safe when parallel test workers race to create it).
DO $$
BEGIN
    CREATE ROLE {dwh}_analyst NOLOGIN;
EXCEPTION WHEN duplicate_object OR unique_violation THEN
    NULL;
END $$;

GRANT USAGE ON SCHEMA {dwh} TO {dwh}_analyst;
GRANT SELECT ON {dwh}.v_safety_by_study_month TO {dwh}_analyst;
GRANT SELECT (ae_id, study_id, study_code, subject_id, arm, site_id, country_code, onset_date, year_month,
              meddra_pt, soc, grade, is_serious, is_related, outcome, days_to_resolution)
    ON {dwh}.v_adverse_event_detail TO {dwh}_analyst;

-- Visit fact. Grain: one row per planned visit. Range-partitioned by visit month.

CREATE TABLE {dwh}.fact_visit (
    visit_id        text NOT NULL,
    subject_sk      int NOT NULL,
    study_sk        int NOT NULL,
    visit_date      date NOT NULL,
    visit_date_key  int NOT NULL,
    visit_type      text,
    status          text,
    is_completed    boolean
) PARTITION BY RANGE (visit_date);

DO $$
DECLARE m date;
BEGIN
    FOR m IN SELECT generate_series(date '2025-01-01', date '2026-12-01', interval '1 month')::date LOOP
        EXECUTE format('CREATE TABLE %I.%I PARTITION OF %I.fact_visit FOR VALUES FROM (%L) TO (%L)',
                       '{dwh}', 'fact_visit_' || to_char(m, 'YYYYMM'), '{dwh}',
                       m, (m + interval '1 month')::date);
    END LOOP;
END $$;
CREATE TABLE {dwh}.fact_visit_default PARTITION OF {dwh}.fact_visit DEFAULT;

INSERT INTO {dwh}.fact_visit
SELECT v.visit_id,
       ds.subject_sk,
       dst.study_sk,
       v.visit_date,
       to_char(v.visit_date, 'YYYYMMDD')::int,
       v.visit_type,
       v.status,
       v.status = 'COMPLETED'
FROM {latest}.visit v
JOIN {dwh}.dim_subject ds ON ds.subject_id = v.subject_id
JOIN {dwh}.dim_study dst ON dst.study_id = ds.study_id;

CREATE INDEX ON {dwh}.fact_visit (subject_sk);
ANALYZE {dwh}.fact_visit;

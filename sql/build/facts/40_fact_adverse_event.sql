-- Adverse event fact. Grain: one row per adverse event (current version).
-- Range-partitioned by onset month; the DEFAULT partition must stay empty.
-- site_sk is a point-in-time lookup: the site version valid at 00:00 UTC on the onset date.

CREATE TABLE {dwh}.fact_adverse_event (
    ae_id               text NOT NULL,
    subject_sk          int NOT NULL,
    study_sk            int NOT NULL,
    site_sk             int NOT NULL,
    onset_date          date NOT NULL,
    onset_date_key      int NOT NULL,
    meddra_pt           text,
    soc                 text,
    grade               smallint,
    is_serious          boolean,
    is_related          boolean,
    outcome             text,
    days_to_resolution  int,
    last_changed_at     timestamptz
) PARTITION BY RANGE (onset_date);

DO $$
DECLARE m date;
BEGIN
    FOR m IN SELECT generate_series(date '2025-01-01', date '2026-12-01', interval '1 month')::date LOOP
        EXECUTE format('CREATE TABLE %I.%I PARTITION OF %I.fact_adverse_event FOR VALUES FROM (%L) TO (%L)',
                       '{dwh}', 'fact_adverse_event_' || to_char(m, 'YYYYMM'), '{dwh}',
                       m, (m + interval '1 month')::date);
    END LOOP;
END $$;
CREATE TABLE {dwh}.fact_adverse_event_default PARTITION OF {dwh}.fact_adverse_event DEFAULT;

INSERT INTO {dwh}.fact_adverse_event
SELECT ae.ae_id,
       ds.subject_sk,
       dst.study_sk,
       dsi.site_sk,
       ae.onset_date,
       to_char(ae.onset_date, 'YYYYMMDD')::int,
       ae.meddra_pt,
       ae.soc,
       ae.grade,
       ae.serious,
       ae.related,
       ae.outcome,
       ae.resolved_date - ae.onset_date,
       ae.last_changed_at
FROM {latest}.adverse_event ae
JOIN {dwh}.dim_subject ds ON ds.subject_id = ae.subject_id
JOIN {dwh}.dim_study dst ON dst.study_id = ds.study_id
JOIN {dwh}.dim_site dsi
  ON dsi.site_id = ds.site_id
 AND ae.onset_date::timestamptz >= dsi.valid_from
 AND ae.onset_date::timestamptz < dsi.valid_to;

CREATE INDEX ON {dwh}.fact_adverse_event (subject_sk);
CREATE INDEX ON {dwh}.fact_adverse_event (study_sk);
ANALYZE {dwh}.fact_adverse_event;

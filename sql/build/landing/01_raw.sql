-- Landing zone ({raw}): the CDC feed exactly as delivered. Append-only, duplicates included,
-- no keys. Partitioned by ingestion month, the way a lake lands files per day or month.
-- Business columns are copied from the source tables; delivery metadata is added.

DROP SCHEMA IF EXISTS {raw} CASCADE;
CREATE SCHEMA {raw};

CREATE TABLE {raw}.study_events (
    LIKE {src}.study,
    change_seq   bigint NOT NULL,
    op           char(1) NOT NULL CHECK (op IN ('I', 'U', 'D')),
    changed_at   timestamptz NOT NULL,
    ingested_at  timestamptz NOT NULL,
    batch_id     text NOT NULL
) PARTITION BY RANGE (ingested_at);

CREATE TABLE {raw}.site_events (
    LIKE {src}.site,
    change_seq   bigint NOT NULL,
    op           char(1) NOT NULL CHECK (op IN ('I', 'U', 'D')),
    changed_at   timestamptz NOT NULL,
    ingested_at  timestamptz NOT NULL,
    batch_id     text NOT NULL
) PARTITION BY RANGE (ingested_at);

CREATE TABLE {raw}.subject_events (
    LIKE {src}.subject,
    change_seq   bigint NOT NULL,
    op           char(1) NOT NULL CHECK (op IN ('I', 'U', 'D')),
    changed_at   timestamptz NOT NULL,
    ingested_at  timestamptz NOT NULL,
    batch_id     text NOT NULL
) PARTITION BY RANGE (ingested_at);

CREATE TABLE {raw}.visit_events (
    LIKE {src}.visit,
    change_seq   bigint NOT NULL,
    op           char(1) NOT NULL CHECK (op IN ('I', 'U', 'D')),
    changed_at   timestamptz NOT NULL,
    ingested_at  timestamptz NOT NULL,
    batch_id     text NOT NULL
) PARTITION BY RANGE (ingested_at);

CREATE TABLE {raw}.adverse_event_events (
    LIKE {src}.adverse_event,
    change_seq   bigint NOT NULL,
    op           char(1) NOT NULL CHECK (op IN ('I', 'U', 'D')),
    changed_at   timestamptz NOT NULL,
    ingested_at  timestamptz NOT NULL,
    batch_id     text NOT NULL
) PARTITION BY RANGE (ingested_at);

-- One partition per ingestion month, plus a DEFAULT that must stay empty.
DO $$
DECLARE
    t text;
    m date;
BEGIN
    FOREACH t IN ARRAY ARRAY['study_events', 'site_events', 'subject_events', 'visit_events',
                             'adverse_event_events'] LOOP
        FOR m IN SELECT generate_series(date '2024-12-01', date '2026-12-01', interval '1 month')::date LOOP
            EXECUTE format('CREATE TABLE %I.%I PARTITION OF %I.%I FOR VALUES FROM (%L) TO (%L)',
                           '{raw}', t || '_' || to_char(m, 'YYYYMM'), '{raw}', t,
                           m::timestamptz, (m + interval '1 month')::timestamptz);
        END LOOP;
        EXECUTE format('CREATE TABLE %I.%I PARTITION OF %I.%I DEFAULT', '{raw}', t || '_default', '{raw}', t);
    END LOOP;
END $$;

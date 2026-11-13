-- A tiny landing zone for hand-built visit events: one plain raw table, no partitions, so edge cases and property tests can rebuild in milliseconds.
DROP SCHEMA IF EXISTS {raw} CASCADE;
CREATE SCHEMA {raw};
CREATE TABLE {raw}.visit_events (
    visit_id     text NOT NULL,
    subject_id   text NOT NULL,
    visit_type   text NOT NULL,
    visit_date   date NOT NULL,
    status       text NOT NULL,
    change_seq   bigint NOT NULL,
    op           char(1) NOT NULL CHECK (op IN ('I', 'U', 'D')),
    changed_at   timestamptz NOT NULL,
    ingested_at  timestamptz NOT NULL,
    batch_id     text NOT NULL
);

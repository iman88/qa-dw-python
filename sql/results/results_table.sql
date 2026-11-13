-- Where every monitoring run stores its results: one row per check per run, kept for trends and audit.
CREATE SCHEMA IF NOT EXISTS qa_monitor;
CREATE TABLE IF NOT EXISTS qa_monitor.check_results (
    run_id          text NOT NULL,
    ran_at          timestamptz NOT NULL,
    as_of           timestamptz NOT NULL,
    target          text NOT NULL,
    check_id        text NOT NULL,
    kind            text NOT NULL,
    passed          boolean NOT NULL,
    offending_rows  integer NOT NULL,
    sample          text
);

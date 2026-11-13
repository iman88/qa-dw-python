-- Every recorded test outcome, one row per test per run, for flaky-test tracking and trends.
CREATE SCHEMA IF NOT EXISTS qa_monitor;
CREATE TABLE IF NOT EXISTS qa_monitor.test_results (
    run_id      text NOT NULL,
    ran_at      timestamptz NOT NULL,
    test_id     text NOT NULL,
    outcome     text NOT NULL,
    duration_s  numeric NOT NULL,
    worker      text NOT NULL
);

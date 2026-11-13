-- Every GenAI evaluation run: one row per metric, with the versions that make runs comparable.
CREATE SCHEMA IF NOT EXISTS qa_monitor;
CREATE TABLE IF NOT EXISTS qa_monitor.genai_eval_runs (
    run_id            text NOT NULL,
    ran_at            timestamptz NOT NULL,
    engine            text NOT NULL,
    model             text NOT NULL,
    prompt_version    text NOT NULL,
    evalset_version   text NOT NULL,
    metric            text NOT NULL,
    passed            integer NOT NULL,
    total             integer NOT NULL,
    p95_latency_ms    numeric NOT NULL,
    cost_usd          numeric NOT NULL
);

-- Study dimension, type 1 (current values only), from the latest layer.

CREATE TABLE {dwh}.dim_study (
    study_sk          serial PRIMARY KEY,
    study_id          text NOT NULL,
    study_code        text,
    phase             text,
    therapeutic_area  text,
    start_date_key    int
);

INSERT INTO {dwh}.dim_study (study_id, study_code, phase, therapeutic_area, start_date_key)
SELECT study_id, study_code, phase, therapeutic_area, to_char(start_date, 'YYYYMMDD')::int
FROM {latest}.study
ORDER BY study_id;

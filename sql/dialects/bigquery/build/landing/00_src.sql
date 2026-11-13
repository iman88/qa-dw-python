-- BigQuery: the operational source copy. Keys are declared NOT ENFORCED (BigQuery uses them only to optimise queries), which is exactly why the rule checks test them.
CREATE SCHEMA IF NOT EXISTS {src};

CREATE OR REPLACE TABLE {src}.study (
    study_id STRING NOT NULL, study_code STRING NOT NULL, title STRING NOT NULL, phase STRING NOT NULL,
    therapeutic_area STRING NOT NULL, start_date DATE NOT NULL,
    PRIMARY KEY (study_id) NOT ENFORCED
);
CREATE OR REPLACE TABLE {src}.site (
    site_id STRING NOT NULL, study_id STRING NOT NULL, country_code STRING NOT NULL, investigator STRING NOT NULL,
    status STRING NOT NULL,
    PRIMARY KEY (site_id) NOT ENFORCED
);
CREATE OR REPLACE TABLE {src}.subject (
    subject_id STRING NOT NULL, site_id STRING NOT NULL, study_id STRING NOT NULL, arm STRING NOT NULL,
    sex STRING NOT NULL, birth_year INT64 NOT NULL, enrolled_on DATE NOT NULL, withdrawn_on DATE,
    PRIMARY KEY (subject_id) NOT ENFORCED
);
CREATE OR REPLACE TABLE {src}.visit (
    visit_id STRING NOT NULL, subject_id STRING NOT NULL, visit_type STRING NOT NULL, visit_date DATE NOT NULL,
    status STRING NOT NULL,
    PRIMARY KEY (visit_id) NOT ENFORCED
);
CREATE OR REPLACE TABLE {src}.adverse_event (
    ae_id STRING NOT NULL, subject_id STRING NOT NULL, meddra_pt STRING NOT NULL, soc STRING NOT NULL,
    grade INT64 NOT NULL, serious BOOL NOT NULL, related BOOL NOT NULL, onset_date DATE NOT NULL,
    resolved_date DATE, outcome STRING NOT NULL,
    PRIMARY KEY (ae_id) NOT ENFORCED
);

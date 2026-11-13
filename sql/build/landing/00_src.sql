-- Operational source system ({src}): current state only, with its own constraints, like an OLTP database.
-- This is the system of record every other layer is reconciled against.

DROP SCHEMA IF EXISTS {src} CASCADE;
CREATE SCHEMA {src};

CREATE TABLE {src}.study (
    study_id          text PRIMARY KEY,
    study_code        text NOT NULL UNIQUE,
    title             text NOT NULL,
    phase             text NOT NULL CHECK (phase IN ('I', 'II', 'III', 'IV')),
    therapeutic_area  text NOT NULL,
    start_date        date NOT NULL
);

CREATE TABLE {src}.site (
    site_id       text PRIMARY KEY,
    study_id      text NOT NULL REFERENCES {src}.study,
    country_code  char(2) NOT NULL,
    investigator  text NOT NULL,
    status        text NOT NULL CHECK (status IN ('ACTIVE', 'SUSPENDED', 'CLOSED'))
);

CREATE TABLE {src}.subject (
    subject_id    text PRIMARY KEY,
    site_id       text NOT NULL REFERENCES {src}.site,
    study_id      text NOT NULL REFERENCES {src}.study,
    arm           text NOT NULL CHECK (arm IN ('PLACEBO', 'DOSE_LOW', 'DOSE_HIGH')),
    sex           char(1) NOT NULL CHECK (sex IN ('F', 'M')),
    birth_year    int NOT NULL,
    enrolled_on   date NOT NULL,
    withdrawn_on  date
);

CREATE TABLE {src}.visit (
    visit_id    text PRIMARY KEY,
    subject_id  text NOT NULL REFERENCES {src}.subject,
    visit_type  text NOT NULL,
    visit_date  date NOT NULL,
    status      text NOT NULL CHECK (status IN ('SCHEDULED', 'COMPLETED', 'MISSED'))
);

CREATE TABLE {src}.adverse_event (
    ae_id          text PRIMARY KEY,
    subject_id     text NOT NULL REFERENCES {src}.subject,
    meddra_pt      text NOT NULL,
    soc            text NOT NULL,
    grade          smallint NOT NULL CHECK (grade BETWEEN 1 AND 5),
    serious        boolean NOT NULL,
    related        boolean NOT NULL,
    onset_date     date NOT NULL,
    resolved_date  date,
    outcome        text NOT NULL
);

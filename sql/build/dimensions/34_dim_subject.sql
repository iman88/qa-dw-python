-- Subject dimension, type 1, from the latest layer. Age and withdrawal flag are derived here.

CREATE TABLE {dwh}.dim_subject (
    subject_sk         serial PRIMARY KEY,
    subject_id         text NOT NULL,
    study_id           text NOT NULL,
    site_id            text NOT NULL,
    arm                text,
    sex                text,
    age_at_enrolment   int,
    enrolled_date_key  int,
    is_withdrawn       boolean
);

INSERT INTO {dwh}.dim_subject (subject_id, study_id, site_id, arm, sex, age_at_enrolment, enrolled_date_key,
                               is_withdrawn)
SELECT subject_id, study_id, site_id, arm, sex,
       extract(YEAR FROM enrolled_on)::int - birth_year,
       to_char(enrolled_on, 'YYYYMMDD')::int,
       withdrawn_on IS NOT NULL
FROM {latest}.subject
ORDER BY subject_id;

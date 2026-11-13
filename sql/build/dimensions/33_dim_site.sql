-- Site dimension, type 2: one row per version of a site, valid in [valid_from, valid_to).
-- Built from the history layer, so a change of investigator or status opens a new version.

CREATE TABLE {dwh}.dim_site (
    site_sk       serial PRIMARY KEY,
    site_id       text NOT NULL,
    study_id      text NOT NULL,
    country_code  text,
    investigator  text,
    status        text,
    valid_from    timestamptz NOT NULL,
    valid_to      timestamptz NOT NULL,
    is_current    boolean NOT NULL
);

INSERT INTO {dwh}.dim_site (site_id, study_id, country_code, investigator, status, valid_from, valid_to,
                            is_current)
SELECT site_id, study_id, country_code, investigator, status, valid_from, valid_to, is_current
FROM {hist}.site_history
WHERE NOT is_deleted
ORDER BY site_id, valid_from;

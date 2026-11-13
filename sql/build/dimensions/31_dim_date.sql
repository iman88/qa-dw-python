-- Calendar dimension, one row per day.

CREATE TABLE {dwh}.dim_date AS
SELECT to_char(d, 'YYYYMMDD')::int        AS date_key,
       d::date                            AS full_date,
       extract(YEAR FROM d)::int          AS year,
       extract(QUARTER FROM d)::int       AS quarter,
       extract(MONTH FROM d)::int         AS month,
       to_char(d, 'YYYY-MM')              AS year_month,
       extract(ISODOW FROM d)::int        AS iso_day_of_week
FROM generate_series(date '2024-01-01', date '2027-12-31', interval '1 day') AS d;

ALTER TABLE {dwh}.dim_date ADD PRIMARY KEY (date_key);
ALTER TABLE {dwh}.dim_date ALTER COLUMN full_date SET NOT NULL;

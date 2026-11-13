-- BigQuery: calendar dimension from GENERATE_DATE_ARRAY (Postgres uses generate_series).
CREATE OR REPLACE TABLE {dwh}.dim_date AS
SELECT CAST(FORMAT_DATE('%Y%m%d', d) AS INT64) AS date_key,
       d AS full_date,
       EXTRACT(YEAR FROM d) AS year,
       EXTRACT(QUARTER FROM d) AS quarter,
       EXTRACT(MONTH FROM d) AS month,
       FORMAT_DATE('%Y-%m', d) AS year_month,
       EXTRACT(DAYOFWEEK FROM d) AS day_of_week
FROM UNNEST(GENERATE_DATE_ARRAY(DATE '2024-01-01', DATE '2027-12-31')) AS d;

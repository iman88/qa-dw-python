-- Rule: in {table}, the date key and the partition date describe the same day.

SELECT {date_column}, {date_key_column}
FROM {schema}.{table}
WHERE {date_key_column} <> to_char({date_column}, 'YYYYMMDD')::int

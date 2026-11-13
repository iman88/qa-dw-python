-- Rule: no text value anywhere in {schema} looks like an e-mail address, a phone number or a Romanian national ID (CNP). Scans every text column of every table and view.
SELECT table_name, column_name, matches
FROM (
    SELECT c.table_name, c.column_name,
           (xpath('/row/n/text()', query_to_xml(format(
               'SELECT count(*) AS n FROM %I.%I WHERE %I ~ %L',
               c.table_schema, c.table_name, c.column_name,
               '([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|\+?[0-9][0-9 ()-]{8,}[0-9]|\m[1-8][0-9]{12}\M)'
           ), false, true, '')))[1]::text::int AS matches
    FROM information_schema.columns c
    WHERE c.table_schema = '{schema}' AND c.data_type IN ('text', 'character varying', 'character')
) scanned
WHERE matches > 0

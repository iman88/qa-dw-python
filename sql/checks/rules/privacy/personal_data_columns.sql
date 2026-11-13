-- Rule: no column in {schema} has a name that suggests personal data (birth, email, phone, address, national id, name...) unless it is on the approved list ({approved}).
SELECT c.table_name, c.column_name
FROM information_schema.columns c
WHERE c.table_schema = '{schema}'
  AND c.column_name ~* '(birth|dob|e_?mail|phone|mobile|address|street|zip|postcode|national_id|cnp|ssn|passport|first_?name|last_?name|surname|initials|investigator)'
  AND c.table_name || '.' || c.column_name NOT IN ({approved})

-- Rule (BigQuery): no column in {schema} has a name that suggests personal data unless it is on the approved list ({approved}).
SELECT table_name, column_name
FROM {schema}.INFORMATION_SCHEMA.COLUMNS
WHERE REGEXP_CONTAINS(LOWER(column_name),
        r'(birth|dob|e_?mail|phone|mobile|address|street|zip|postcode|national_id|cnp|ssn|passport|first_?name|last_?name|surname|initials|investigator)')
  AND CONCAT(table_name, '.', column_name) NOT IN ({approved})

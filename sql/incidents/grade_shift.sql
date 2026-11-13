-- A source system upgrade started reporting every recent adverse event as grade 4 (a silent mapping change).
UPDATE {dwh}.fact_adverse_event SET grade = 4 WHERE onset_date >= date '2026-04-01'

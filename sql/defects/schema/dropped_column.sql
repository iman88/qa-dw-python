-- A refactoring dropped a column that downstream reports still read (data reconciliation cannot see it)
ALTER TABLE {dwh}.fact_visit DROP COLUMN status

---
name: add-dq-rule
description: Add a data quality check (keys, history/SCD2, partitions, values, or custom SQL) as a rule file under sql/checks/rules/, use it from a feature with a data table, and add a defect that proves it works. Use when asked to test a new table, constraint or modelling rule.
---

# Add a data quality check

A rule is one SQL file under `sql/checks/rules/<category>/` (keys, history, partitions, values, privacy) that
returns the **offending rows**. No rows = pass. Its first comment line is its description.

1. **Reuse a rule file if one fits.** Identifiers come from the scenario's data table:
   ```gherkin
   When I run the check "sql/checks/rules/keys/referential_integrity.sql" with:
     | layer | fact       | fk         | dim         | pk         |
     | dwh   | fact_visit | subject_sk | dim_subject | subject_sk |
   Then it finds no offending rows
   ```
   `layer` picks the schema (`{schema}` in the file); every other column fills a `{placeholder}`.
2. **Otherwise write a new file** in the right category. Select columns that help a human debug
   (keys, the bad value, the expected value). Use `{dwh}`-style placeholders, never schema names.
3. **Use it in a feature** (04 history and latest, 05 star schema, 06 partitions) with the path in the step.
4. **Add it to the catalogue** in `src/clinical_dq/dq/checks.py` so `clinical-dq check`, the catalogue
   scenario and the defect tests run it.
5. **Add a defect** in `sql/defects/<category>/` that violates it (must change at least one row) and a
   row in `tests/features/08_defect_injection.feature` naming the check path and its target.
6. `pytest -m "history or star or partition or mutation"` and ruff.

Rules worth knowing: latest has one row per key and no deleted keys; history has one row per
`change_seq`, contiguous versions and exactly one open-ended current version; facts have a unique
grain, every key resolves, SCD2 lookups are point in time, and every row sits in a planned monthly
partition, never DEFAULT.

## Also

- The new SQL must run on BigQuery: if it uses anything Postgres-specific, add a counterpart at
  `sql/dialects/bigquery/<same path>` or a reason in `sql/dialects/bigquery/manifest.json`
  (`pytest -m quality` checks this).
- Keep `sqlfluff lint sql` clean, and tag any new feature with a requirement from `docs/requirements.json`.

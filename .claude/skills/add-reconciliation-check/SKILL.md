---
name: add-reconciliation-check
description: Add a source-to-target reconciliation (row level or aggregate) as a folder with source.sql and target.sql, put it in the reconciliation feature and prove it can fail. Use when asked to reconcile a new table, column, layer pair, view or KPI.
---

# Add a reconciliation

A reconciliation is a folder `sql/checks/recon/<category>/<name>/` with `source.sql` and `target.sql`.
Both run, rows are matched by the business key and compared column by column. Aggregates are grouped
queries keyed by the group. Categories: latest, history, dimensions, facts, aggregates, views.

1. **Pick the pair and the key.** Source = the layer you trust (usually `{src}`); target = the layer
   under test. The key must be unique on both sides; duplicates are reported as failures.
2. **Write both files.** First line of `source.sql`: a plain-English description (it is shown in the
   report). Use layer placeholders `{src} {raw} {hist} {latest} {dwh}`, never schema names, so the check
   also runs on the mutation copy. Same column names on both sides; alias where the warehouse renames
   (`ae.serious AS is_serious`). Derive on the source side what the pipeline derives (ages, flags).
   Use LEFT JOINs on the target side so an orphan row shows as a mismatch instead of disappearing.
3. **Add a scenario row** in `tests/features/03_reconciliation.feature` with the folder path and key.
   The coverage scenario fails until every folder is in the feature.
4. **Add it to the catalogue** (`src/clinical_dq/recon/checks.py`, `_catalogue`) so `clinical-dq check`
   and the defect tests run it.
5. **Prove it can fail:** add `sql/defects/<category>/<name>.sql` (first line = the real-world cause)
   and a row in `tests/features/08_defect_injection.feature`. Try it: `clinical-dq inject <name>`,
   `clinical-dq check`, then `clinical-dq build`.
6. `pytest -m "recon or mutation"` and ruff.

At production volumes, push the comparison into SQL (hash each row, compare hashes, then fetch only
mismatching keys) and keep `ReconResult` as the result so features and report stay the same.

## Also

- The new SQL must run on BigQuery: if it uses anything Postgres-specific, add a counterpart at
  `sql/dialects/bigquery/<same path>` or a reason in `sql/dialects/bigquery/manifest.json`
  (`pytest -m quality` checks this).
- Keep `sqlfluff lint sql` clean, and tag any new feature with a requirement from `docs/requirements.json`.

---
name: run-suite
description: Start Postgres, run the data and AI test suite (all of it, a feature, a requirement, a tag or one scenario), the linters, and find the reports. Use when asked to run, rerun or debug tests in this repo.
---

# Run the suite

1. `docker compose up -d` (Postgres 18 on host port 55432). `docker compose ps` must show `healthy`.
2. Use the venv (`.venv/Scripts/python` on Windows, `.venv/bin/python` elsewhere). First time:
   `python -m venv .venv` then `pip install -c constraints.txt -e ".[test,dev]"`. Versions are pinned;
   never upgrade as a side effect of other work.
3. Run. The session fixture rebuilds every layer, so no manual build is needed.

| Goal | Command |
|---|---|
| Everything | `pytest` (or `pytest -n auto` in parallel; each worker gets its own database) |
| One area | `pytest -m recon` (tags: data schema recon history star partition warehouse mutation genai incremental edge pushdown monitoring compliance genai_scale property quality unit) |
| One requirement | `pytest -m REQ_05` |
| Only what a change affects | `clinical-dq affected --since origin/main` prints the pytest command |
| One scenario | `pytest -k "deleted"` |
| Record outcomes (flaky tracking) | `pytest --record-results` |
| GenAI against Claude | `GENAI_PROVIDER=claude GENAI_FALLBACK=off pytest -m "genai or genai_scale or genai_live"` (costs money: ask first) |

4. Quality gate (same as CI): `ruff check src tests conftest.py`, `ruff format --check src tests conftest.py`,
   `sqlfluff lint sql`, `mypy`, `pytest -n auto`.
5. One HTML report: `reports/data-quality-report.html` (requirements, reconciliations, checks, defects, GenAI).
   Auditor files: `traceability-matrix.csv`, `data-quality-report.json`, `cucumber.json`; `clinical-dq evidence`
   freezes them with SHA-256 hashes.
6. When something fails, use the triage-data-failure skill. Do not change a check or its expected values to
   make it pass without saying so; a red data test usually means the pipeline is wrong.

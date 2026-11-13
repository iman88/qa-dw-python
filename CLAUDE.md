# CLAUDE.md

Data and AI test automation for a clinical R&D warehouse. Python 3.15, Postgres 18 in Docker,
pytest-bdd (Gherkin), SQLAlchemy + psycopg 3, Hypothesis, pytest-xdist, Playwright APIRequestContext
for HTTP services, FastAPI narrative service, sqlglot for BigQuery, Anthropic SDK (optional).

## Layout

- `sql/` every query and script, one per file, in category folders (build/, incremental/,
  checks/{rules,recon,recon_engine,monitoring,build_compare,schema}/, contracts/, defects/, incidents/,
  schema_changes/, fixtures/, monitoring/, queries/, dialects/bigquery/). Paths are repo-relative (`sql/...`).
- `tests/features/01-15_*.feature` readable specifications; each names the SQL files it runs and
  carries @REQ_xx tags from `docs/requirements.json`.
- `tests/steps/` step definitions (`sql_steps.py` = generic SQL steps), registered in root `conftest.py`.
- `tests/property/`, `tests/quality/`, `tests/unit/` for property-based, tooling and no-database tests.
- `src/clinical_dq/` loader, pipeline (full + incremental), engines, catalogues, monitor, GenAI, CLI.

## Rules

- The warehouse is tested in SQL. No web service on top of SQL. Playwright only for HTTP/UI services
  around the warehouse (today: the narrative service).
- New SQL goes in a file under the right category, never inline in Python. Short SQL may be inline in a
  feature docstring. Use layer placeholders `{src} {raw} {hist} {latest} {dwh}`.
- A check returns offending rows; its first comment line is its description.
- Every new check needs a defect in `sql/defects/<category>/` and a row in `08_defect_injection.feature`.
  Never loosen a check to get green without saying so.
- Every new SQL file must run on BigQuery: portable, a counterpart in `sql/dialects/bigquery/`, or a
  reason in its `manifest.json` (`tests/quality/test_bigquery_dialect.py` enforces it).
- Every feature carries a requirement tag; every requirement is covered (`14_compliance` enforces it).
- The repo must work without AI: template summariser by default, Claude optional with fallback.
  Live Claude runs cost money; ask first.
- Versions are pinned (pyproject `==`, constraints.txt, Postgres digest, Actions by SHA, Python 3.15.2).
  Install with `pip install -c constraints.txt -e ".[test,dev]"`. Upgrades are a deliberate change.
- CI must stay closed to outsiders: no `pull_request` / `pull_request_target` triggers, read-only token.
- Done means: `docker compose up -d`, `ruff check src tests conftest.py`, `ruff format --check src tests
  conftest.py`, `sqlfluff lint sql`, `mypy`, `pytest -n auto` all green, README updated.
- Synthetic data only. No real patient, client or employer data or metrics.
- No git commit or push without the user's explicit approval.

## graphify

This project has a knowledge graph at graphify-out/ (rebuild with `graphify update .`, AST-only, no LLM cost).

- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use
  `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain are not enough.
- After modifying code, run `graphify update .` to keep the graph current.
- graphify is optional: install it (`graphify install`) to get its skill; local hooks live in the git-ignored
  `.claude/settings.local.json`, so contributors without graphify see no errors.

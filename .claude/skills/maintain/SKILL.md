---
name: maintain
description: Run the periodic maintenance of this repo - check every row of the README "Maintenance & planned updates" table against current releases, apply the updates that are due one at a time with the full quality gate green, and refresh the table. Use when asked for maintenance, upgrades, or "is anything outdated".
---

# Maintain the repo

The README section "🔄 Maintenance & planned updates" is the checklist. Work through it row by row.

1. **Check what is current** (do not rely on memory):
   - Python 3.15 patch: `gh api "repos/python/cpython/tags?per_page=100" --jq '.[].name' | grep -E '^v3\.15\.[0-9]+$' | sort -V | tail -1`
   - PostgreSQL 18 minor: `gh api "repos/postgres/postgres/tags?per_page=100" --jq '.[].name' | grep -E '^REL_18_[0-9]+$' | sort -V | tail -1`,
     then `docker pull postgres:18.<n>-alpine` and take the digest from `docker image inspect`.
   - GitHub Actions: `gh api repos/actions/<name>/releases/latest --jq .tag_name`, then the commit SHA of that tag.
   - Python packages: `pip list --outdated`.
   - Claude models: the claude-api skill's model table.
2. **Apply one update at a time**, each as its own change:
   - change the pin (`.python-version`, `pyproject.toml`, `docker-compose.yml` + `ci.yml`, or the action SHA);
   - upgrade in the venv; run `ruff check src tests conftest.py`, `ruff format --check src tests conftest.py`,
     `sqlfluff lint sql`, `mypy`, `pytest -n auto`;
   - regenerate `constraints.txt` with `pip freeze --exclude-editable` (keep the header) and review the diff.
3. **Time-based items:** fact partitions end Dec 2026 and the calendar dimension Dec 2027; extend them before
   real data reaches those dates (build scripts, `partition_plan` months, contracts unchanged).
4. **Claude model change:** run `clinical-dq eval` with the new model (costs money: ask first) and switch only if
   no metric regresses.
5. **Update the table**: new current versions, new end-of-life dates, urgency (✅ when nothing is due), and the
   "Checked on" date. Summarise for the user what changed and what is still due.

Never upgrade as a side effect of other work, and never commit or push without the user's approval.

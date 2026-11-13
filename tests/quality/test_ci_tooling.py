"""The CI tooling itself: test selection by changed files, and flaky-test tracking."""

from __future__ import annotations

import pytest

from clinical_dq.affected import affected_markers, pytest_command
from clinical_dq.db.client import SqlClient
from clinical_dq.results import flaky_tests, record_test_results

pytestmark = pytest.mark.quality


@pytest.mark.parametrize(
    ("changed", "expected"),
    [
        (
            ["sql/checks/recon/facts/fact_adverse_event_vs_source/source.sql"],
            {"recon", "pushdown", "mutation"},
        ),
        (["sql/checks/rules/partitions/partition_plan.sql"], {"partition", "mutation"}),
        (["sql/incidents/grade_shift.sql"], {"monitoring"}),
        (["sql/queries/genai/subject_events_dwh.sql"], {"genai"}),
        (["tests/features/06_partitions.feature"], {"partition"}),
    ],
)
def test_a_change_selects_the_features_that_name_it(changed, expected) -> None:
    assert expected <= set(affected_markers(changed))


def test_a_change_to_shared_code_runs_everything() -> None:
    assert affected_markers(["sql/build/facts/40_fact_adverse_event.sql"]) is None
    assert pytest_command(affected_markers(["src/clinical_dq/sql.py"])) == "pytest"


def test_a_documentation_change_runs_nothing() -> None:
    assert affected_markers(["README.md", "docs/img/data-quality-report.png"]) == []


def test_flaky_tests_are_the_ones_that_both_passed_and_failed(db: SqlClient) -> None:
    db.execute("DROP TABLE IF EXISTS qa_monitor.test_results")
    for run, outcome in enumerate(["passed", "failed", "passed", "passed"]):
        record_test_results(
            db,
            [
                {"test_id": "test_stable", "outcome": "passed", "duration_s": 0.1, "worker": "gw0"},
                {"test_id": "test_flaky", "outcome": outcome, "duration_s": 0.2, "worker": "gw1"},
            ],
            run_id=f"run-{run}",
        )
    flaky = flaky_tests(db, runs=10)
    assert [(f["test_id"], f["passed"], f["failed"]) for f in flaky] == [("test_flaky", 3, 1)]
    db.execute("DROP TABLE qa_monitor.test_results")

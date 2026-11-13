"""Steps that describe the seeded test data with exact figures."""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, then

from clinical_dq.config import Settings
from clinical_dq.db.client import SqlClient
from tests.steps.sql_steps import show


@given(parsers.parse("the data was generated with seed {seed:d} and {subjects:d} subjects per study"))
def default_data(settings: Settings, seed: int, subjects: int) -> None:
    if (settings.data_seed, settings.subjects_per_study) != (seed, subjects):
        pytest.skip(f"exact figures apply to seed {seed} with {subjects} subjects per study")


@then("these queries return these values:")
def queries_return(db: SqlClient, datatable: list[list[str]]) -> None:
    header, *rows = datatable
    wrong = []
    for row in rows:
        spec = dict(zip(header, row, strict=True))
        actual = show(db.scalar(spec["query"]))
        if actual != spec["value"]:
            wrong.append(f"{spec['what']}: {actual}, expected {spec['value']}  ({spec['query']})")
    assert not wrong, "\n".join(wrong)

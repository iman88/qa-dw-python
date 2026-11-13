"""The reconciliation engine on its own, no database."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from clinical_dq.recon.engine import diff_rows, normalise

pytestmark = pytest.mark.unit

SRC = [
    {"id": 1, "grade": 2, "onset": date(2025, 1, 1)},
    {"id": 2, "grade": 3, "onset": date(2025, 1, 2)},
    {"id": 3, "grade": 1, "onset": date(2025, 1, 3)},
]


def test_identical_rows_match() -> None:
    result = diff_rows("same", SRC, [dict(r) for r in SRC], ["id"])
    assert result.passed
    assert result.compared_columns == ("grade", "onset")


def test_missing_and_extra_keys_are_reported() -> None:
    target = [SRC[0], SRC[1], {"id": 4, "grade": 1, "onset": date(2025, 1, 4)}]
    result = diff_rows("keys", SRC, target, ["id"])
    assert not result.passed
    assert result.missing_in_target == [(3,)]
    assert result.extra_in_target == [(4,)]


def test_value_mismatch_names_key_and_column() -> None:
    target = [SRC[0], {**SRC[1], "grade": 4}, SRC[2]]
    result = diff_rows("values", SRC, target, ["id"])
    assert result.mismatches == [{"key": 2, "column": "grade", "source": 3, "target": 4}]


def test_duplicate_keys_fail_even_when_counts_look_fine() -> None:
    target = [SRC[0], SRC[1], SRC[1]]  # 3 rows, same as source, but id 3 lost and id 2 doubled
    result = diff_rows("dupes", SRC, target, ["id"])
    assert result.duplicate_in_target == [(2,)]
    assert result.missing_in_target == [(3,)]
    assert not result.passed


def test_composite_keys() -> None:
    src = [{"study": "A", "month": "2025-01", "n": 5}]
    tgt = [{"study": "A", "month": "2025-01", "n": 6}]
    result = diff_rows("agg", src, tgt, ["study", "month"])
    assert result.mismatches[0]["key"] == ["A", "2025-01"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("1.5000"), 1.5),
        (2.0000001, 2.0),
        (date(2025, 1, 1), "2025-01-01"),
        (datetime(2025, 1, 1, 12, 0), "2025-01-01T12:00:00"),
        ("  padded ", "padded"),
        (None, None),
    ],
)
def test_normalise(value, expected) -> None:
    assert normalise(value) == expected

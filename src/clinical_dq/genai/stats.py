"""Statistics for GenAI evaluation: is a drop in pass rate real, and does a judge agree with humans?"""

from __future__ import annotations

import math
from dataclasses import dataclass


def _normal_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


@dataclass(frozen=True)
class Comparison:
    before: float
    after: float
    z: float
    p_value: float
    regression: bool


def regression_test(
    passed_before: int,
    total_before: int,
    passed_after: int,
    total_after: int,
    alpha: float = 0.05,
    min_drop: float = 0.01,
) -> Comparison:
    """One-sided two-proportion z-test: did the pass rate really drop, or is it noise?

    A regression needs both a statistically significant drop (p < alpha) and a drop of at least
    ``min_drop`` (one percentage point by default), so tiny but "significant" changes on huge sets
    do not block a release.
    """
    p1, p2 = passed_before / total_before, passed_after / total_after
    pooled = (passed_before + passed_after) / (total_before + total_after)
    se = math.sqrt(pooled * (1 - pooled) * (1 / total_before + 1 / total_after))
    z = 0.0 if se == 0 else (p1 - p2) / se
    p_value = 1 - _normal_cdf(z)
    return Comparison(p1, p2, round(z, 3), round(p_value, 4), p_value < alpha and (p1 - p2) >= min_drop)


def cohen_kappa(human: list[bool], judge: list[bool]) -> float:
    """Agreement between two raters beyond chance: 1 = perfect, 0 = no better than chance."""
    n = len(human)
    observed = sum(h == j for h, j in zip(human, judge, strict=True)) / n
    p_h, p_j = sum(human) / n, sum(judge) / n
    expected = p_h * p_j + (1 - p_h) * (1 - p_j)
    return 1.0 if expected == 1 else round((observed - expected) / (1 - expected), 3)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct / 100
    low, high = math.floor(k), math.ceil(k)
    return ordered[low] + (ordered[high] - ordered[low]) * (k - low)

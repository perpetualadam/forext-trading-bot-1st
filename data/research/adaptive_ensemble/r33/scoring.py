"""Frozen R.33 stub decision. This module does not read market files."""

from __future__ import annotations

from typing import Any, Sequence


def decide_stub(
    mean: float | None,
    overlapping_mean: float | None,
    interval: tuple[float, float] | None,
    shuffle_p95: float,
    coin_p95: float,
    median_spread: float,
    quarters: Sequence[dict[str, Any]],
) -> dict[str, str]:
    """Apply the frozen first-match label. A numeric pass stays inconclusive."""
    if mean is None:
        return {"classification": "INCONCLUSIVE", "rule": "missing_primary_mean"}
    if mean <= 0:
        return {"classification": "EVALUABLE_NO_CREDIBLE_EDGE", "rule": "nonpositive_mean"}
    if overlapping_mean is None:
        return {"classification": "INCONCLUSIVE", "rule": "overlapping_missing"}
    if overlapping_mean < 0:
        return {"classification": "INCONCLUSIVE", "rule": "overlapping_opposite_sign"}
    if interval is None or interval[0] <= 0:
        return {"classification": "INCONCLUSIVE", "rule": "interval_includes_zero_or_missing"}
    eligible = [row for row in quarters if int(row["count"]) >= 30]
    positive = sum(1 for row in eligible if float(row["mean"]) > 0)
    if (
        mean > shuffle_p95
        and mean > coin_p95
        and len(eligible) >= 3
        and positive >= 3
        and mean > median_spread
    ):
        return {"classification": "INCONCLUSIVE", "rule": "exposed_period"}
    return {"classification": "EVALUABLE_NO_CREDIBLE_EDGE", "rule": "remaining_gate"}

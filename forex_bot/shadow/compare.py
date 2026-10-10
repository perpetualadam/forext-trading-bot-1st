"""Compare Track A outputs to historical fills without fabricating agreement rates.

A live fill is not proof that every eligible signal produced an order.
AI vote, RL action, and quant eligibility are not stored on trades rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from forex_bot.shadow.tracks import TRACK_A, refuse_mixed_stats


@dataclass
class ComparisonReport:
    valid_reference_decisions: int = 0
    exact_matches: int = 0
    mismatches: int = 0
    missing_references: int = 0
    unreproducible: int = 0
    compared_fields: tuple[str, ...] = ()
    agreement_rate: float | None = None
    limitation: str = (
        "Live trades store strategy, direction, size, and prices only. "
        "They do not store AI vote, RL action, or bar-level eligibility. "
        "Agreement rates are omitted unless overlapping Track A rows exist "
        "for a field with a trustworthy reference."
    )
    by_field: dict[str, dict[str, int]] = field(default_factory=dict)
    simulated: bool = True
    track: str = TRACK_A


def compare_track_a_to_fills(
    track_a_rows: list[dict[str, Any]],
    fill_rows: list[dict[str, Any]],
    *,
    key_fields: tuple[str, ...] = ("symbol", "time_key"),
    compare_fields: tuple[str, ...] = ("strategy", "direction"),
) -> ComparisonReport:
    """Match on timestamp+symbol keys only. No interpolation. No fill-as-signal assumption."""
    refuse_mixed_stats([str(r.get("track") or TRACK_A) for r in track_a_rows] or [TRACK_A])
    report = ComparisonReport(compared_fields=compare_fields)
    if not fill_rows:
        report.limitation += " No fill rows supplied."
        return report
    index: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in track_a_rows:
        key = tuple(row.get(k) for k in key_fields)
        if any(v is None for v in key):
            continue
        index[key] = row
    for fill in fill_rows:
        key = tuple(fill.get(k) for k in key_fields)
        if any(v is None for v in key):
            report.missing_references += 1
            continue
        cand = index.get(key)
        if cand is None:
            report.missing_references += 1
            continue
        if str(cand.get("reason") or "") == "NOT_REPRODUCIBLE":
            report.unreproducible += 1
            continue
        report.valid_reference_decisions += 1
        matched = True
        for field_name in compare_fields:
            left = cand.get(field_name)
            right = fill.get(field_name)
            bucket = report.by_field.setdefault(field_name, {"match": 0, "mismatch": 0})
            if left is None or right is None:
                report.missing_references += 1
                matched = False
                continue
            if str(left).upper() == str(right).upper():
                bucket["match"] += 1
            else:
                bucket["mismatch"] += 1
                matched = False
        if matched:
            report.exact_matches += 1
        else:
            report.mismatches += 1
    if report.valid_reference_decisions > 0:
        report.agreement_rate = report.exact_matches / report.valid_reference_decisions
    else:
        report.agreement_rate = None
    return report

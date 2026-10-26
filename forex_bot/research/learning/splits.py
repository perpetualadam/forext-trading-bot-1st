"""Chronological folds with an embargo for overlapping outcome windows."""

from __future__ import annotations

from forex_bot.research.learning.protocol import (
    EMBARGO_BARS,
    TRAIN_FRACTION,
    VALIDATION_FRACTION,
    WARMUP_BARS,
)


def chronological_split(
    row_count: int,
    *,
    warmup: int = WARMUP_BARS,
    embargo: int = EMBARGO_BARS,
    train_fraction: float = TRAIN_FRACTION,
    validation_fraction: float = VALIDATION_FRACTION,
) -> dict:
    """Index ranges whose labels cannot reach the next fold."""
    if row_count < warmup + embargo * 3:
        raise ValueError("series_too_short_for_embargoed_split")
    if train_fraction <= 0 or validation_fraction <= 0 or train_fraction + validation_fraction >= 1:
        raise ValueError("invalid_fractions")
    train_cut = int(row_count * train_fraction)
    valid_cut = int(row_count * (train_fraction + validation_fraction))
    train = range(warmup, train_cut - embargo)
    validation = range(train_cut, valid_cut - embargo)
    test = range(valid_cut, row_count - embargo)
    if not train or not validation or not test:
        raise ValueError("empty_fold")
    if max(train) + embargo >= min(validation) or max(validation) + embargo >= min(test):
        raise ValueError("embargo_failed")
    return {
        "train": (train.start, train.stop),
        "validation": (validation.start, validation.stop),
        "test": (test.start, test.stop),
        "warmup_bars": warmup,
        "embargo_bars": embargo,
        "research_exposed_not_an_untouched_holdout": True,
    }

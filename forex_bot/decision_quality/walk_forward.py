"""Chronological train / validation / test splits. No shuffling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from forex_bot.decision_quality.outcomes import TradeRecord


@dataclass(frozen=True)
class TimeSplit:
    name: str
    start: datetime
    end: datetime


def chronological_splits(
    records: list[TradeRecord],
    *,
    train_frac: float = 0.50,
    valid_frac: float = 0.25,
) -> dict[str, list[TradeRecord]]:
    """Split closed trades by entry time. Later periods are unseen."""
    ordered = sorted(
        [t for t in records if t.entry_time is not None],
        key=lambda t: t.entry_time,
    )
    n = len(ordered)
    if n == 0:
        return {"train": [], "valid": [], "test": []}
    i_train = max(1, int(n * train_frac))
    i_valid = max(i_train + 1, int(n * (train_frac + valid_frac)))
    if i_valid >= n:
        i_valid = n
    return {
        "train": ordered[:i_train],
        "valid": ordered[i_train:i_valid],
        "test": ordered[i_valid:],
    }


def assert_splits_isolated(splits: dict[str, list[TradeRecord]]) -> None:
    """Every later split starts at or after the previous split's last entry."""
    train = splits.get("train") or []
    valid = splits.get("valid") or []
    test = splits.get("test") or []
    if train and valid and valid[0].entry_time < train[-1].entry_time:
        raise AssertionError("validation leaked into training time")
    if valid and test and test[0].entry_time < valid[-1].entry_time:
        raise AssertionError("test leaked into validation time")
    if train and test and test[0].entry_time < train[-1].entry_time:
        raise AssertionError("test leaked into training time")


def walk_forward_windows(
    records: list[TradeRecord],
    *,
    folds: int = 3,
) -> list[tuple[list[TradeRecord], list[TradeRecord]]]:
    """Expanding train, next fold as test."""
    ordered = sorted(records, key=lambda t: t.entry_time)
    n = len(ordered)
    if n < folds * 2:
        return []
    fold_size = max(1, n // (folds + 1))
    out: list[tuple[list[TradeRecord], list[TradeRecord]]] = []
    for i in range(folds):
        train_end = fold_size * (i + 1)
        test_end = min(n, train_end + fold_size)
        train = ordered[:train_end]
        test = ordered[train_end:test_end]
        if train and test:
            out.append((train, test))
    return out

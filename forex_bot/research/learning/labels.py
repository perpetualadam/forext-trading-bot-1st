"""Future outcome labels. These columns must stay out of the feature frame."""

from __future__ import annotations

import pandas as pd

from forex_bot.research.learning.protocol import BAR_SECONDS, LABEL_PROTOCOL_VERSION, PRIMARY_HORIZON_BARS

LABEL_COLUMNS = (
    "outcome_evaluable",
    "outcome_timestamp",
    "midpoint_return",
    "directional_outcome",
    "buy_cost_adjusted_return",
    "sell_cost_adjusted_return",
)


def label_outcomes(frame: pd.DataFrame, horizon: int = PRIMARY_HORIZON_BARS) -> pd.DataFrame:
    """Label bar T with the close exactly `horizon` bars later, when that bar exists."""
    if horizon < 1:
        raise ValueError("horizon_must_be_positive")
    future_time = frame["time"].shift(-horizon)
    expected = pd.to_timedelta(horizon * BAR_SECONDS, unit="s")
    aligned = future_time.notna() & ((future_time - frame["time"]) == expected)
    mid = (frame["bid_close"] + frame["ask_close"]) / 2.0
    future_mid = mid.shift(-horizon)
    future_bid = frame["bid_close"].shift(-horizon)
    future_ask = frame["ask_close"].shift(-horizon)
    prices_ok = future_bid.notna() & future_ask.notna() & (frame["ask_close"] > 0) & (frame["bid_close"] > 0)
    evaluable = aligned & prices_ok
    midpoint_return = future_mid / mid - 1.0
    buy_cost = future_bid / frame["ask_close"] - 1.0
    sell_cost = (frame["bid_close"] - future_ask) / frame["bid_close"]
    direction = pd.Series(pd.NA, index=frame.index, dtype="object")
    direction = direction.mask(evaluable & (midpoint_return > 0), "up")
    direction = direction.mask(evaluable & (midpoint_return < 0), "down")
    direction = direction.mask(evaluable & (midpoint_return == 0), "flat")
    return pd.DataFrame(
        {
            "outcome_evaluable": evaluable.fillna(False),
            "outcome_timestamp": future_time.where(evaluable),
            "midpoint_return": midpoint_return.where(evaluable),
            "directional_outcome": direction.where(evaluable),
            "buy_cost_adjusted_return": buy_cost.where(evaluable),
            "sell_cost_adjusted_return": sell_cost.where(evaluable),
            "label_protocol_version": LABEL_PROTOCOL_VERSION,
            "horizon_bars": horizon,
        }
    )


def labels_isolated(features: pd.DataFrame, labels: pd.DataFrame) -> bool:
    shared = set(features.columns) & set(LABEL_COLUMNS)
    return not shared

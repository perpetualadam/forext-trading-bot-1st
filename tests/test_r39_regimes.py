"""Offline tests for the R.39 regime research. They use synthetic bars."""

from __future__ import annotations

import numpy as np
import pandas as pd

from forex_bot.research.learning.features import leaky_future_return, prefix_matches
from forex_bot.research.learning.regimes import (
    DATASET_SHA256,
    PIP_SIZE,
    PROTOCOL,
    classify_regimes,
    promotion_allowed,
    reward_to_risk,
    select_signals,
    simulate,
    strategy_signals,
)


def _clock(count: int) -> np.ndarray:
    return pd.date_range("2026-01-05", periods=count, freq="5min", tz="UTC").as_unit("ns").astype("int64").to_numpy(copy=True)


def _flat(count: int, price: float = 1.10, spread: float = 0.0001) -> dict:
    mid = np.full(count, price)
    half = spread / 2.0
    return {
        "mid": mid,
        "open": mid.copy(),
        "high": mid + 0.00005,
        "low": mid - 0.00005,
        "spread": np.full(count, spread),
        "time_ns": _clock(count),
        "bid_open": mid - half,
        "ask_open": mid + half,
        "bid_high": mid,
        "bid_low": mid - spread,
        "ask_high": mid + spread,
        "ask_low": mid,
        "bid_close": mid - half,
        "ask_close": mid + half,
    }


def _simulate(market: dict, direction: np.ndarray, kind: str = "trend") -> dict:
    count = len(direction)
    return simulate(
        direction,
        kind,
        time_ns=market["time_ns"],
        bid_open=market["bid_open"],
        ask_open=market["ask_open"],
        bid_high=market["bid_high"],
        bid_low=market["bid_low"],
        ask_high=market["ask_high"],
        ask_low=market["ask_low"],
        bid_close=market["bid_close"],
        ask_close=market["ask_close"],
        spread=market["spread"],
        atr=np.full(count, 0.001),
        support=np.full(count, 1.0),
        resistance=np.full(count, 1.2),
        pip=0.0001,
    )


def test_hashes_pip_and_no_promotion() -> None:
    assert DATASET_SHA256["USD_JPY"].startswith("e1b0d349")
    assert PIP_SIZE["USD_JPY"] == 0.01
    assert PIP_SIZE["GBP_USD"] == 0.0001
    assert promotion_allowed() is False
    assert PROTOCOL["mapping"]["UNCERTAIN"] == "NO_TRADE"
    assert PROTOCOL["production_authorised"] is False


def test_warmup_and_flat_market_stay_uncertain() -> None:
    market = _flat(80)
    labels = classify_regimes(market["mid"], market["high"], market["low"], market["spread"], market["time_ns"])
    assert set(labels[:48]) == {"UNCERTAIN"}
    assert labels[-1] == "UNCERTAIN"


def test_regime_label_does_not_change_when_later_bars_are_removed() -> None:
    market = _flat(90)
    market["mid"] = np.linspace(1.10, 1.12, 90)
    market["high"] = market["mid"] + 0.00005
    market["low"] = market["mid"] - 0.00005
    full = classify_regimes(market["mid"], market["high"], market["low"], market["spread"], market["time_ns"])
    short = classify_regimes(market["mid"][:70], market["high"][:70], market["low"][:70], market["spread"][:70], market["time_ns"][:70])
    assert full[69] == short[69]
    leaked = full.copy()
    leaked[:-1] = np.where(np.diff(market["mid"]) > 0, "TREND", "RANGE")
    assert leaked[69] != short[69]


def test_breakout_boundary_excludes_the_current_bar() -> None:
    market = _flat(80)
    market["high"][-1] = 1.20
    market["mid"][-1] = 1.10
    signals = strategy_signals(market["mid"], market["open"], market["high"], market["low"], market["spread"])
    assert int(signals["breakout"][-1]) == 0


def test_selector_keeps_no_trade_when_uncertain() -> None:
    regimes = np.array(["UNCERTAIN", "TREND", "RANGE"])
    signals = {
        "trend": np.array([1, 1, 1], dtype=np.int8),
        "range": np.array([1, -1, -1], dtype=np.int8),
        "breakout": np.array([1, 1, 1], dtype=np.int8),
    }
    assert list(select_signals(regimes, signals)) == [0, 1, -1]


def test_reward_to_risk_rejects_a_stop_on_the_wrong_side() -> None:
    assert reward_to_risk(1.10, 1.09, 1.12, 1) == 2.0
    assert reward_to_risk(1.10, 1.11, 1.12, 1) is None


def test_buy_entry_is_the_next_ask_and_ambiguous_bars_lose() -> None:
    market = _flat(90, spread=0.00002)
    direction = np.zeros(90, dtype=np.int8)
    direction[60] = 1
    quiet = _simulate(market, direction)
    assert quiet["trades"] and quiet["trades"][0]["direction"] == 1
    market["bid_low"][61] = 1.0
    market["bid_high"][61] = 1.2
    hit = _simulate(market, direction)
    assert hit["trades"][0]["outcome"] == "ambiguous_intrabar"
    assert hit["trades"][0]["net"] < 0.0


def test_a_gap_blocks_entry_and_does_not_open_the_next_signal() -> None:
    market = _flat(90, spread=0.00002)
    market["time_ns"][65:] += 3_600_000_000_000
    direction = np.zeros(90, dtype=np.int8)
    direction[64] = 1
    direction[70] = 1
    result = _simulate(market, direction)
    assert result["rejected"]["gap"] >= 1
    assert all(row["decision"] != 64 for row in result["trades"])
    assert len(result["trades"]) <= 1


def test_operational_flags_and_fail_closed_controls_stay_unchanged() -> None:
    from forex_bot.ai_ensemble import _quant_stub_vote
    from forex_bot.rl_agent import RLAgent
    from forex_bot.strategy_meta import strategies

    assert all(not item.active and not item.authorised_for_live for item in strategies.values())
    vote = _quant_stub_vote({"returns": 0.01})
    assert vote["allow"] is False and vote["reason"] == "quant_stub_removed"
    assert RLAgent().decide("unseen") == "UNAVAILABLE"
    assert ".active = True" not in open("forex_bot/research/learning/regimes.py", encoding="utf-8").read()
    frame = pd.DataFrame(
        {
            "time": pd.date_range("2026-01-05", periods=40, freq="5min", tz="UTC"),
            "bid_open": 1.1,
            "bid_high": 1.2,
            "bid_low": 1.0,
            "bid_close": 1.1,
            "ask_open": 1.2,
            "ask_high": 1.3,
            "ask_low": 1.1,
            "ask_close": 1.2,
            "volume": 10.0,
        }
    )
    assert prefix_matches(leaky_future_return, frame, 30) is False

"""Protect diagnostic sign conventions. Does not run historical backtests."""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from forex_bot.decision_quality.execution_sim import r_multiple
from forex_bot.decision_quality.invariants import signed_pips
from forex_bot.decision_quality.outcomes import forward_returns, observe_after_stop
from forex_bot.decision_quality.walk_forward import assert_splits_isolated, chronological_splits
from forex_bot.decision_quality.snapshot import DecisionSnapshot
from forex_bot.decision_quality.outcomes import TradeRecord


def _snap(side: str, ts: datetime) -> DecisionSnapshot:
    return DecisionSnapshot(
        timestamp=ts,
        symbol="EUR_USD",
        side=side,
        strategy="trend",
        horizon="swing",
        route="test",
        entry_price=1.1,
        reference_mid=1.1,
        decision=side,
    )


def _trade(side: str, ts: datetime) -> TradeRecord:
    snap = _snap(side, ts)
    return TradeRecord(
        snapshot=snap,
        entry_time=ts,
        exit_time=ts + timedelta(minutes=5),
        exit_reason="sl",
        exit_price=1.099,
        realised_pips=-10.0,
        realised_r=-1.0,
        win=False,
        mfe_pips=0.0,
        mae_pips=10.0,
        mfe_r=0.0,
        mae_r=1.0,
        mfe_atr=0.0,
        mae_atr=2.0,
        time_to_mfe_min=None,
        time_to_mae_min=None,
        time_in_trade_min=5.0,
        sl_distance_pips=10.0,
        tp_distance_pips=20.0,
        sl_over_atr=2.0,
        tp_over_atr=4.0,
        max_tp_progress=0.0,
        ambiguous=False,
    )


def test_direction_adjusted_forward_signs():
    assert signed_pips("EUR_USD", "BUY", 1.1000, 1.1010) > 0
    assert signed_pips("EUR_USD", "BUY", 1.1000, 1.0990) < 0
    assert signed_pips("EUR_USD", "SELL", 1.1000, 1.0990) > 0
    assert signed_pips("EUR_USD", "SELL", 1.1000, 1.1010) < 0
    jpy_buy = signed_pips("USD_JPY", "BUY", 150.00, 150.10)
    assert jpy_buy == 10.0
    t0 = datetime(2025, 1, 2, 8, 0)
    df = pd.DataFrame(
        [
            {"time": t0, "open": 1.1000, "high": 1.1002, "low": 1.0998, "close": 1.1000},
            {"time": t0 + timedelta(minutes=5), "open": 1.1000, "high": 1.1012, "low": 1.0999, "close": 1.1010},
        ]
    )
    buy_fwd = forward_returns(df, 0, "EUR_USD", "BUY", 1.1000)
    sell_fwd = forward_returns(df, 0, "EUR_USD", "SELL", 1.1000)
    assert buy_fwd["5m_pips"] > 0
    assert sell_fwd["5m_pips"] < 0
    assert buy_fwd["5m_pips"] == -sell_fwd["5m_pips"]


def test_r_normalization_uses_stop_distance():
    assert r_multiple(10.0, 10.0) == 1.0
    assert r_multiple(20.0, 10.0) == 2.0
    assert r_multiple(-10.0, 10.0) == -1.0
    assert r_multiple(5.0, 0.0) is None


def test_mfe_mae_signs_are_nonnegative_by_convention():
    t = _trade("BUY", datetime(2025, 1, 2, 8, 0))
    assert t.mfe_pips >= 0
    assert t.mae_pips >= 0
    assert t.mfe_r >= 0
    assert t.mae_r >= 0


def test_post_stop_r_thresholds_use_sl_distance():
    t0 = datetime(2025, 1, 2, 8, 0)
    rows = []
    px = 1.1000
    for i in range(8):
        rows.append(
            {
                "time": t0 + timedelta(minutes=5 * i),
                "open": px,
                "high": px + 0.0020,
                "low": px - 0.0001,
                "close": px + 0.0015,
            }
        )
        px += 0.0015
    df = pd.DataFrame(rows)
    out = observe_after_stop(
        df,
        exit_idx=0,
        symbol="EUR_USD",
        side="BUY",
        entry=1.1000,
        take_profit=1.1020,
        sl_distance_pips=10.0,
    )
    assert out["plus_0_5r"] is True
    assert out["plus_1r"] is True
    assert out["reached_original_tp"] is True


def test_sma_periods_and_independent_recompute():
    from forex_bot.indicators import compute_indicators

    closes = [1.1000 + 0.0001 * i for i in range(120)]
    df = pd.DataFrame(
        {
            "time": [datetime(2025, 1, 2, 8, 0) + timedelta(minutes=5 * i) for i in range(120)],
            "open": closes,
            "high": [c + 0.0002 for c in closes],
            "low": [c - 0.0002 for c in closes],
            "close": closes,
        }
    )
    ind = compute_indicators(df, lookback=100)
    i = 119
    assert float(ind["ma_fast"].iloc[i]) == pytest.approx(sum(closes[i - 9 : i + 1]) / 10)
    assert float(ind["ma_slow"].iloc[i]) == pytest.approx(sum(closes[i - 49 : i + 1]) / 50)
    ret = (closes[i] - closes[i - 1]) / closes[i - 1]
    assert float(ind["close"].pct_change().iloc[i]) == pytest.approx(ret)


def test_history_at_excludes_next_bar():
    from forex_bot.decision_quality.data import history_at

    t0 = datetime(2025, 1, 2, 8, 0)
    df = pd.DataFrame(
        {
            "time": [t0 + timedelta(minutes=5 * i) for i in range(10)],
            "open": [1.1] * 10,
            "high": [1.1] * 10,
            "low": [1.1] * 10,
            "close": [1.10 + i * 0.001 for i in range(10)],
        }
    )
    window = history_at(df, 4)
    assert len(window) == 5
    assert window["time"].iloc[-1] == df["time"].iloc[4]
    assert float(window["close"].iloc[-1]) == float(df["close"].iloc[4])
    assert float(df["close"].iloc[5]) != float(window["close"].iloc[-1])


def test_chronological_partitions_do_not_leak():
    t0 = datetime(2025, 1, 2, 8, 0)
    trades = [_trade("BUY", t0 + timedelta(minutes=5 * i)) for i in range(20)]
    splits = chronological_splits(trades)
    assert_splits_isolated(splits)
    assert len(splits["train"]) + len(splits["valid"]) + len(splits["test"]) == 20
    assert splits["train"][-1].entry_time <= splits["valid"][0].entry_time
    assert splits["valid"][-1].entry_time <= splits["test"][0].entry_time

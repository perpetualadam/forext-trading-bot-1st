"""Offline engine: no leakage, deterministic, production parity, post-stop, isolation."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from forex_bot.ai_ensemble import _quant_stub_vote
from forex_bot.decision_quality.data import history_at
from forex_bot.decision_quality.engine import run_symbol_backtest
from forex_bot.decision_quality.forensics import classify_loss
from forex_bot.decision_quality.isolation import assert_package_cannot_write_broker
from forex_bot.decision_quality.outcomes import observe_after_stop
from forex_bot.decision_quality.research_features import htf_trend_labels, resample_closed_ohlc
from forex_bot.decision_quality.signal import evaluate_signal, production_quant_decision
from forex_bot.decision_quality.walk_forward import assert_splits_isolated, chronological_splits
from forex_bot.indicators import compute_indicators


def _ohlcv(n: int, *, start: float = 1.1000, drift: float = 0.00002, vol: float = 0.00012) -> pd.DataFrame:
    t0 = datetime(2024, 1, 2, 8, 0, 0)
    rows = []
    px = start
    for i in range(n):
        px = px + drift
        hi = px + vol
        lo = px - vol
        rows.append(
            {
                "time": t0 + timedelta(minutes=5 * i),
                "open": px - drift / 2,
                "high": hi,
                "low": lo,
                "close": px,
            }
        )
    return pd.DataFrame(rows)


def test_package_cannot_reach_broker_writes():
    assert assert_package_cannot_write_broker() == []
    import forex_bot.decision_quality.engine as engine

    src = open(engine.__file__, encoding="utf-8").read()
    assert "oanda_exec" not in src
    assert "execute_trade" not in src


def test_signal_uses_only_historical_indicators(monkeypatch):
    df = _ohlcv(120)
    seen_n = []

    real = compute_indicators

    def wrapped(frame, lookback=None, **kwargs):
        seen_n.append(len(frame))
        return real(frame, lookback=lookback, **kwargs)

    monkeypatch.setattr("forex_bot.decision_quality.signal.compute_indicators", wrapped)
    window = history_at(df, 90)
    evaluate_signal("EUR_USD", window, df["time"].iloc[90].to_pydatetime(), seed=1)
    assert seen_n
    assert max(seen_n) == 91


def test_quant_direction_matches_production_stub():
    df = _ohlcv(80, drift=0.00005)
    vote = production_quant_decision(df, lookback=50)
    last = compute_indicators(df, lookback=50).iloc[-1]
    expected = _quant_stub_vote(
        {
            "price": float(last["close"]),
            "ma_fast": float(last["ma_fast"]),
            "ma_slow": float(last["ma_slow"]),
            "returns": float(compute_indicators(df, lookback=50)["close"].pct_change().iloc[-1]),
            "atr": float(last["atr"]),
        }
    )
    assert vote["direction"] == expected["direction"]
    assert vote["allow"] == expected["allow"]


def test_htf_uses_only_closed_bars():
    df = _ohlcv(80)
    asof = df["time"].iloc[20].to_pydatetime()  # 09:40
    h1 = resample_closed_ohlc(df, "1h", asof)
    if not h1.empty:
        last_start = pd.Timestamp(h1["time"].iloc[-1])
        assert last_start + pd.Timedelta(hours=1) <= pd.Timestamp(asof)
    labels = htf_trend_labels(df.iloc[:21], asof)
    assert "H1" in labels


def test_engine_is_deterministic_and_respects_invariants(monkeypatch):
    monkeypatch.setenv("USE_ATR_STOPS", "false")
    monkeypatch.setenv("SL_FALLBACK_PIPS", "20")
    monkeypatch.setenv("HYBRID_EUR_USD", "false")
    df = _ohlcv(220, drift=0.00003)
    a = run_symbol_backtest("EUR_USD", df, warmup=80, seed=7, apply_fx_week=False)
    b = run_symbol_backtest("EUR_USD", df, warmup=80, seed=7, apply_fx_week=False)
    assert len(a.trades) == len(b.trades)
    assert [t.snapshot.side for t in a.trades] == [t.snapshot.side for t in b.trades]
    assert [t.realised_r for t in a.trades] == [t.realised_r for t in b.trades]
    for t in a.trades:
        if t.snapshot.side == "BUY":
            assert t.snapshot.take_profit > t.snapshot.entry_price
            assert t.snapshot.stop_loss < t.snapshot.entry_price
        elif t.snapshot.side == "SELL":
            assert t.snapshot.take_profit < t.snapshot.entry_price
            assert t.snapshot.stop_loss > t.snapshot.entry_price


def test_walk_forward_is_chronological(monkeypatch):
    monkeypatch.setenv("USE_ATR_STOPS", "false")
    monkeypatch.setenv("HYBRID_EUR_USD", "false")
    df = _ohlcv(260, drift=0.00002)
    res = run_symbol_backtest("EUR_USD", df, warmup=80, seed=3, apply_fx_week=False)
    splits = chronological_splits(res.trades)
    assert_splits_isolated(splits)
    if splits["train"] and splits["test"]:
        assert splits["test"][0].entry_time >= splits["train"][-1].entry_time


def test_post_stop_tracks_later_tp():
    t0 = datetime(2024, 1, 2, 10, 0, 0)
    # SELL stopped out, then price falls to original TP.
    rows = []
    prices = [1.1000, 1.1004, 1.1008, 1.0992, 1.0980]
    for i, px in enumerate(prices):
        rows.append(
            {
                "time": t0 + timedelta(minutes=5 * i),
                "open": px,
                "high": px + 0.0002,
                "low": px - 0.0002,
                "close": px,
            }
        )
    df = pd.DataFrame(rows)
    post = observe_after_stop(
        df,
        exit_idx=2,
        symbol="EUR_USD",
        side="SELL",
        entry=1.1000,
        take_profit=1.0982,
        sl_distance_pips=8.0,
    )
    assert post["reached_original_tp"] is True
    assert post["moved_original_direction"] is True


def test_loss_classifier_is_deterministic():
    from forex_bot.decision_quality.outcomes import TradeRecord
    from forex_bot.decision_quality.snapshot import DecisionSnapshot

    snap = DecisionSnapshot(
        timestamp=datetime(2024, 1, 2, 12, 0, 0),
        symbol="GBP_USD",
        side="SELL",
        strategy="swing_mean_reversion",
        horizon="swing",
        route="quant_stub+select_strategy",
        entry_price=1.34742,
        reference_mid=1.34742,
        decision="SELL",
        h1_trend="BULLISH",
        h4_trend="BULLISH",
        htf_agreement="against_h1|against_h4|h1_h4_agree",
        regime="TRENDING_UP",
        session="london",
        pre_move_atr=0.2,
    )
    rec = TradeRecord(
        snapshot=snap,
        entry_time=snap.timestamp,
        exit_time=snap.timestamp,
        exit_reason="sl",
        exit_price=1.34783,
        realised_pips=-4.1,
        realised_r=-1.0,
        win=False,
        mfe_pips=0.5,
        mae_pips=4.1,
        mfe_r=0.1,
        mae_r=1.0,
        mfe_atr=0.1,
        mae_atr=0.8,
        time_to_mfe_min=5,
        time_to_mae_min=10,
        time_in_trade_min=15,
        sl_distance_pips=4.1,
        tp_distance_pips=8.1,
        sl_over_atr=0.8,
        tp_over_atr=1.6,
        max_tp_progress=0.06,
        ambiguous=False,
        post_stop={"reached_original_tp": True, "plus_1r": True, "moved_original_direction": True},
    )
    assert classify_loss(rec) == "possible_stop_too_tight"
    rec.post_stop = {"reached_original_tp": False, "plus_1r": False, "moved_original_direction": False}
    rec.snapshot.pre_move_atr = 2.0
    assert classify_loss(rec) == "possible_late_entry"

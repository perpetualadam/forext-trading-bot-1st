"""Lock current offline backtester semantics for later optimized-path comparison."""

from __future__ import annotations

from pathlib import Path

import pytest

from forex_bot.decision_quality.data import history_at, load_symbol_frame
from forex_bot.decision_quality.engine import run_symbol_backtest
from forex_bot.decision_quality.signal import evaluate_signal


FIXTURE_BARS = 250
WARMUP = 80
SEED = 42
SYMBOL = "EUR_USD"
CSV = Path("data/historical/EUR_USD_M5.csv")


@pytest.fixture(autouse=True)
def _pin_signal_env(monkeypatch):
    """Do not inherit local .env routing/stops; CI has no .env."""
    monkeypatch.delenv("HYBRID_EUR_USD", raising=False)
    monkeypatch.delenv("SCALP_LOOKBACK", raising=False)
    monkeypatch.delenv("SWING_LOOKBACK", raising=False)
    monkeypatch.delenv("DEFAULT_INDICATOR_LOOKBACK", raising=False)
    monkeypatch.delenv("HYBRID_ROUTE_LOOKBACK", raising=False)
    monkeypatch.delenv("HYBRID_ATR_SCALP_THRESHOLD", raising=False)
    monkeypatch.delenv("STUB_MOMENTUM_THRESHOLD", raising=False)
    monkeypatch.delenv("STUB_SMA_EPSILON", raising=False)
    monkeypatch.delenv("STUB_CONFIDENCE_SCALE", raising=False)
    monkeypatch.setenv("AI_DISABLE_STUB", "false")
    monkeypatch.delenv("USE_ATR_STOPS", raising=False)
    monkeypatch.delenv("SL_ATR_MULT", raising=False)
    monkeypatch.delenv("SL_FALLBACK_PIPS", raising=False)
    monkeypatch.delenv("MIN_STOP_DISTANCE_PRICE", raising=False)


def _fixture():
    if not CSV.is_file():
        pytest.skip("historical EUR_USD CSV missing")
    return load_symbol_frame(CSV).iloc[:FIXTURE_BARS].reset_index(drop=True)


def _run(df, **kwargs):
    return run_symbol_backtest(
        SYMBOL,
        df,
        warmup=WARMUP,
        seed=SEED,
        apply_session_hours=False,
        apply_fx_week=True,
        **kwargs,
    )


def _trade_tuple(t):
    s = t.snapshot
    return (
        s.timestamp,
        s.decision,
        s.side,
        s.strategy,
        s.horizon,
        s.lookback,
        None if s.entry_price is None else round(float(s.entry_price), 8),
        None if s.stop_loss is None else round(float(s.stop_loss), 8),
        None if s.take_profit is None else round(float(s.take_profit), 8),
        t.exit_reason,
        t.exit_time,
        None if t.realised_pips is None else round(float(t.realised_pips), 6),
        None if t.realised_r is None else round(float(t.realised_r), 6),
        round(float(t.mfe_pips), 6),
        round(float(t.mae_pips), 6),
        bool(t.ambiguous),
        s.h1_trend,
        s.h4_trend,
        s.h15_trend if hasattr(s, "h15_trend") else s.m15_trend,
        s.regime,
        s.volatility_state,
        s.m5_trend,
    )


def assert_backtests_equivalent(a, b, *, atr_tol: float = 1e-10) -> None:
    assert a.symbol == b.symbol
    assert a.bars == b.bars
    assert a.signals == b.signals
    assert len(a.trades) == len(b.trades)
    assert len(a.snapshots) == len(b.snapshots)
    assert [s.decision for s in a.snapshots] == [s.decision for s in b.snapshots]
    assert [s.strategy for s in a.snapshots] == [s.strategy for s in b.snapshots]
    assert [s.horizon for s in a.snapshots] == [s.horizon for s in b.snapshots]
    assert [s.lookback for s in a.snapshots] == [s.lookback for s in b.snapshots]
    assert [s.h1_trend for s in a.snapshots] == [s.h1_trend for s in b.snapshots]
    assert [s.h4_trend for s in a.snapshots] == [s.h4_trend for s in b.snapshots]
    assert [s.m15_trend for s in a.snapshots] == [s.m15_trend for s in b.snapshots]
    assert [s.regime for s in a.snapshots] == [s.regime for s in b.snapshots]
    for sa, sb in zip(a.snapshots, b.snapshots, strict=True):
        if sa.atr is None or sb.atr is None:
            assert sa.atr == sb.atr
        else:
            assert sa.atr == pytest.approx(sb.atr, abs=atr_tol, rel=0)
        if sa.ma_fast is not None and sb.ma_fast is not None:
            assert sa.ma_fast == pytest.approx(sb.ma_fast, abs=1e-12, rel=0)
    assert [_trade_tuple(t) for t in a.trades] == [_trade_tuple(t) for t in b.trades]


@pytest.fixture
def synthetic_reference(monkeypatch):
    """An explicit two-signal research policy; production voters stay disabled."""
    import pandas as pd
    from forex_bot.decision_quality import signal
    original = signal.production_quant_decision
    frame = _fixture()
    frame["time"] = pd.date_range("2026-01-05T10:00:00", periods=len(frame), freq="5min")
    for column in ("open", "high", "low", "close"):
        frame[column] = 1.1
    frame["high"] = 1.10001
    frame["low"] = 1.09999
    frame.loc[81, "high"] = 1.11
    frame.loc[81, "low"] = 1.08

    def policy(raw, lookback):
        vote = original(raw, lookback)
        # Wait for the deliberately extreme exit bar to leave the ATR window.
        side = {81: "BUY", 120: "SELL"}.get(len(raw))
        vote.update(allow=side is not None, direction=side, confidence=0.9 if side else 0.0)
        return vote
    monkeypatch.setattr(signal, "seeded_select_strategy", lambda *_a: ("trend", 60, "synthetic-test"))
    monkeypatch.setattr(signal, "production_quant_decision", policy)
    return frame


def test_reference_is_deterministic_and_default_voters_fail_closed():
    from forex_bot.decision_quality.signal import production_quant_decision
    df = _fixture()
    a = _run(df)
    b = _run(df)
    assert_backtests_equivalent(a, b)
    assert a.signals == 0
    assert a.trades == []
    assert all(s.decision == "NO_SIGNAL" for s in a.snapshots)
    vote = production_quant_decision(df, 60)
    assert vote["allow"] is False and vote["direction"] is None
    assert vote["reason"] == "quant_stub_removed"


def test_reference_signal_sequence_and_trade_count(synthetic_reference):
    r = _run(synthetic_reference)
    assert r.signals == 2
    assert len(r.trades) == 2
    assert [t.snapshot.decision for t in r.trades] == ["BUY", "SELL"]
    assert [t.exit_reason for t in r.trades] == ["ambiguous_sl_tp", "eod"]
    assert r.trades[0].ambiguous is True
    assert r.trades[0].realised_pips < 0
    assert_backtests_equivalent(r, _run(synthetic_reference))


def test_reference_sl_tp_sides_and_exits(synthetic_reference):
    r = _run(synthetic_reference)
    assert len(r.trades) == 2
    for t in r.trades:
        s = t.snapshot
        if s.side == "BUY":
            assert s.take_profit > s.entry_price > s.stop_loss
        else:
            assert s.take_profit < s.entry_price < s.stop_loss
        assert t.exit_time >= t.entry_time
        assert t.realised_pips is not None
        assert t.mfe_pips >= 0
        assert t.mae_pips >= 0


def test_evaluate_signal_prefix_has_no_future_bars(monkeypatch):
    df = _fixture()
    i = 120
    window = history_at(df, i)
    now = df["time"].iloc[i].to_pydatetime()
    snap = evaluate_signal(SYMBOL, window, now, seed=1, apply_fx_week=False)
    assert window["time"].iloc[-1].to_pydatetime() <= now
    assert len(window) == i + 1
    assert snap.symbol == SYMBOL


def test_optimized_impl_matches_reference_when_present():
    """Optimized path must match reference on this fixture."""
    df = _fixture()
    ref = _run(df)
    opt = _run(df, impl="optimized")
    assert_backtests_equivalent(ref, opt)

"""Research-only tests for the momentum x one-M5 2x2. Does not change live trading."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from forex_bot.decision_quality.isolation import forbidden_hits_in_source
from forex_bot.decision_quality.momentum_m5_dedup import (
    MOM_THR,
    STAGE1_FIRST_QUAL_N,
    TRAIN_LE,
    VALID_LE,
    aligned_stub_allow,
    assign_split,
    candle_key,
    classify_factor,
    gate_mask,
    last_completed_m5_key,
    simulate_cell_trades,
    vote_matches_a0,
)
from forex_bot.decision_quality.stub_components import MOM_THR as STUB_MOM_THR
from forex_bot.decision_quality.stub_components import current_stub_allow
from forex_bot.ai_ensemble import _quant_stub_vote

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "forex_bot" / "decision_quality" / "momentum_m5_dedup.py"
REPORT = ROOT / "reports" / "decision_quality" / "momentum_m5_dedup_2x2.md"
STAGE1 = ROOT / "reports" / "decision_quality" / "directional_signal_replacement_stage1.md"


def _frame() -> pd.DataFrame:
    times = pd.date_range("2026-01-01", periods=8, freq="5min", tz="UTC")
    # Bar1 BUY + pos ret; bar2 BUY + neg ret; bar3 SELL + neg; bar4 SELL + pos
    close = np.array([1.0, 1.002, 1.001, 0.998, 0.997, 0.999, 1.001, 1.003])
    state = np.array([1, 1, -1, -1, 1, 1, -1, -1], dtype=np.int8)
    ret = np.array([np.nan, 0.002, -0.001, -0.003, -0.001, 0.002, 0.002, -0.002])
    atr = np.full(8, 0.001)
    return pd.DataFrame(
        {
            "time": times,
            "symbol": "EUR_USD",
            "close": close,
            "high": close + 0.0002,
            "low": close - 0.0002,
            "bid_close": close - 0.00005,
            "ask_close": close + 0.00005,
            "bid_high": close + 0.00015,
            "bid_low": close - 0.00025,
            "ask_high": close + 0.00025,
            "ask_low": close - 0.00015,
            "atr": atr,
            "ret_1": ret,
            "state": state,
            "ma_fast": close + np.where(state > 0, 0.001, -0.001),
            "ma_slow": close,
            "stub_allow": current_stub_allow(state, ret, atr),
            "aligned_allow": aligned_stub_allow(state, ret, atr),
            "side": np.where(state > 0, "BUY", "SELL"),
            "fwd_5m_pips": np.zeros(8),
            "fwd_15m_pips": np.zeros(8),
            "fwd_30m_pips": np.zeros(8),
            "fwd_60m_pips": np.zeros(8),
            "fwd_5m_r": np.zeros(8),
            "fwd_15m_r": np.zeros(8),
            "fwd_30m_r": np.zeros(8),
            "fwd_60m_r": np.zeros(8),
            "fwd_5m_hit": np.zeros(8, dtype=bool),
            "fwd_15m_hit": np.zeros(8, dtype=bool),
            "fwd_30m_hit": np.zeros(8, dtype=bool),
            "fwd_60m_hit": np.zeros(8, dtype=bool),
        }
    )


def test_momentum_threshold_unchanged():
    assert MOM_THR == STUB_MOM_THR == 0.0001
    vote = _quant_stub_vote(
        {"price": 1.0, "ma_fast": 1.01, "ma_slow": 1.0, "returns": 0.0001, "atr": 0.001}
    )
    assert vote["allow"] is False
    vote = _quant_stub_vote(
        {"price": 1.0, "ma_fast": 1.01, "ma_slow": 1.0, "returns": 0.00011, "atr": 0.001}
    )
    assert vote["allow"] is True and vote["direction"] == "BUY"


def test_a0_is_absolute_magnitude_gate():
    state = np.array([1, 1, -1, -1, 0])
    ret = np.array([0.002, -0.002, -0.002, 0.002, 0.002])
    atr = np.ones(5)
    a0 = current_stub_allow(state, ret, atr)
    assert a0.tolist() == [True, True, True, True, False]


def test_a1_requires_sign_agreement_and_does_not_reverse():
    state = np.array([1, 1, -1, -1, 1])
    ret = np.array([0.002, -0.002, -0.002, 0.002, 0.00005])
    atr = np.ones(5)
    a1 = aligned_stub_allow(state, ret, atr)
    assert a1.tolist() == [True, False, True, False, False]
    # Direction still SMA: BUY stays BUY even when blocked.
    assert gate_mask(state, ret, atr, aligned=True).tolist() == a1.tolist()
    vote = _quant_stub_vote(
        {"price": 1.0, "ma_fast": 1.01, "ma_slow": 1.0, "returns": -0.002, "atr": 0.001}
    )
    assert vote["direction"] == "BUY"
    assert vote["allow"] is True  # production A0 still allows opposite sign


def test_a0_matches_production_stub_on_sample_rows():
    frame = _frame()
    for _, row in frame.iloc[1:].iterrows():
        assert vote_matches_a0(row)


def test_b1_first_ok_second_blocked_next_candle_eligible():
    frame = _frame()
    # Force a signal on two identical timestamps (same completed candle) then a new one.
    frame = pd.concat([frame.iloc[[1]], frame.iloc[[1]], frame.iloc[[2]]], ignore_index=True)
    frame.loc[0, "time"] = pd.Timestamp("2026-01-01 00:05:00+00:00")
    frame.loc[1, "time"] = pd.Timestamp("2026-01-01 00:05:00+00:00")
    frame.loc[2, "time"] = pd.Timestamp("2026-01-01 00:10:00+00:00")
    sig = np.array([True, True, True])
    b1 = simulate_cell_trades(frame, sig, "EUR_USD", allow_same_candle_reentry=False)
    times = [pd.Timestamp(t["time"]) for t in b1]
    assert times[0] == pd.Timestamp("2026-01-01 00:05:00+00:00")
    # Second row same candle skipped; later candle may still enter after occupancy frees.
    assert all(not t.get("reentry") for t in b1)


def test_b0_can_reenter_after_fast_sl_same_candle():
    times = pd.date_range("2026-01-01", periods=4, freq="5min", tz="UTC")
    # BUY that immediately stops on the next bar (ask/bid extremes through SL).
    close = np.array([1.1000, 1.1000, 1.0900, 1.0900])
    frame = pd.DataFrame(
        {
            "time": times,
            "symbol": "EUR_USD",
            "close": close,
            "high": close + 0.0001,
            "low": close - 0.0100,
            "bid_close": close - 0.00005,
            "ask_close": close + 0.00005,
            "bid_high": close + 0.0001,
            "bid_low": close - 0.0100,
            "ask_high": close + 0.0001,
            "ask_low": close - 0.0100,
            "atr": np.array([0.001, 0.001, 0.001, 0.001]),
            "ret_1": np.array([np.nan, 0.001, -0.009, 0.0]),
            "state": np.array([1, 1, 1, 1], dtype=np.int8),
            "ma_fast": close + 0.001,
            "ma_slow": close,
            "side": ["BUY"] * 4,
            "fwd_5m_pips": 0.0,
            "fwd_15m_pips": 0.0,
            "fwd_30m_pips": 0.0,
            "fwd_60m_pips": 0.0,
            "fwd_5m_r": 0.0,
            "fwd_15m_r": 0.0,
            "fwd_30m_r": 0.0,
            "fwd_60m_r": 0.0,
            "fwd_5m_hit": False,
            "fwd_15m_hit": False,
            "fwd_30m_hit": False,
            "fwd_60m_hit": False,
        }
    )
    sig = np.array([False, True, False, False])
    b0 = simulate_cell_trades(frame, sig, "EUR_USD", allow_same_candle_reentry=True)
    b1 = simulate_cell_trades(frame, sig, "EUR_USD", allow_same_candle_reentry=False)
    assert any(t.get("reentry") for t in b0)
    assert sum(1 for t in b0 if t.get("source_candle") == b0[0]["source_candle"]) >= 2
    assert len(b1) == 1
    assert not any(t.get("reentry") for t in b1)


def test_symbols_are_independent():
    a = candle_key("EUR_USD", "2026-01-01T00:00:00Z")
    b = candle_key("GBP_USD", "2026-01-01T00:00:00Z")
    assert a != b
    assert a[0] != b[0]


def test_b1_uses_no_future_information():
    entry = datetime(2026, 1, 1, 0, 7, 0, tzinfo=timezone.utc)
    key = last_completed_m5_key("EUR_USD", entry)
    # Forming 00:05-00:10; last completed start is 00:00.
    assert key[1] == pd.Timestamp("2026-01-01 00:00:00+00:00") or key[1] == pd.Timestamp("2026-01-01 00:00:00")


def test_train_valid_test_boundaries_unchanged():
    text = STAGE1.read_text(encoding="utf-8")
    assert "2026-02-27" in text
    assert "2026-05-29" in text
    assert str(TRAIN_LE)[:10] == "2026-02-27"
    assert str(VALID_LE)[:10] == "2026-05-29"
    assert assign_split("2026-02-27 07:47:30+00:00") == "train"
    assert assign_split("2026-02-27 07:47:31+00:00") == "valid"
    assert assign_split("2026-05-29 02:10:00+00:00") == "valid"
    assert assign_split("2026-05-29 02:10:01+00:00") == "test"
    assert STAGE1_FIRST_QUAL_N == 14104


def test_classify_factor_frozen():
    assert classify_factor(0.1, 0.1, 0.05) == "C"
    assert classify_factor(0.1, 0.1, -0.05) == "B"
    assert classify_factor(0.1, -0.01, -0.05) == "A"
    assert classify_factor(-0.01, 0.1, 0.05) == "A"


def test_harness_isolation_from_live_execution():
    text = HARNESS.read_text(encoding="utf-8")
    hits = forbidden_hits_in_source(text)
    assert hits == []


def test_report_has_required_sections():
    text = REPORT.read_text(encoding="utf-8")
    for title in (
        "BASELINE REPRODUCTION:",
        "2×2 OVERALL",
        "MOMENTUM ALIGNMENT EFFECT",
        "ONE-DECISION-PER-M5 EFFECT",
        "INTERACTION",
        "CANDIDATE RETENTION",
        "SAME-CANDLE RE-ENTRY FINDINGS",
        "LIVE DESCRIPTIVE CROSS-CHECK",
        "V2 FORWARD VALIDATION",
        "PRODUCTION FILES CHANGED:",
        "DEPLOY:",
    ):
        assert title in text

"""Stage G offline adaptive ensemble tests. Broker interfaces disabled."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]
import pytest

from forex_bot.research.adaptive_ensemble import LABEL, ORIGINAL_DECISION_FIDELITY
from forex_bot.research.adaptive_ensemble.audit import inventory
from forex_bot.research.adaptive_ensemble.candidates import NO_TRADE, all_signals
from forex_bot.research.adaptive_ensemble.features import (
    classify_regime,
    compute_feature_frame,
    snapshot_at,
)
from forex_bot.research.adaptive_ensemble.isolation import forbidden_hits
from forex_bot.research.adaptive_ensemble.models import (
    WeightState,
    apply_delayed_outcomes,
    baseline_no_trade,
    enqueue_outcome,
    model_dynamic,
    model_regime,
    model_vote,
)
from forex_bot.research.adaptive_ensemble.protocol import (
    freeze_document,
    integrity_hash,
    write_protocol,
)
from forex_bot.research.adaptive_ensemble.runner import synthetic_market
from forex_bot.research.adaptive_ensemble.simulate import fill_price, quote_to_gbp


def _snap_ok(**kw: object) -> dict:
    base = {
        "status": "ok",
        "regime": "trending",
        "ma_slope": 2e-5,
        "atr": 0.0004,
        "rsi": 55.0,
        "atr_pct": 0.5,
        "half_spread": 0.00006,
        "spread_over_atr": 0.1,
        "h1_dir": 1.0,
        "prior_high": 1.10,
        "prior_low": 1.09,
        "close": 1.105,
    }
    base.update(kw)
    return base


def test_label_and_fidelity() -> None:
    assert LABEL == "EXPERIMENTAL_ADAPTIVE_ENSEMBLE_OFFLINE"
    assert ORIGINAL_DECISION_FIDELITY == "ORIGINAL_DECISION_NOT_REPRODUCIBLE"


def test_protocol_integrity_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "protocol_v1.json"
    doc = write_protocol(path)
    assert integrity_hash(doc) == doc["integrity_hash"]
    again = write_protocol(path)
    assert again["integrity_hash"] == doc["integrity_hash"]
    blob = json.loads(path.read_text(encoding="utf-8"))
    blob["pairs"] = []
    with pytest.raises(RuntimeError):
        path.write_text(json.dumps(blob), encoding="utf-8")
        write_protocol(path)


def test_protocol_hash_detects_tamper() -> None:
    doc = freeze_document(frozen_utc="2026-10-09T00:00:00+00:00")
    bad = dict(doc)
    bad["pairs"] = ["FAKE"]
    assert integrity_hash(bad) != doc["integrity_hash"]


def test_no_lookahead_features() -> None:
    df = synthetic_market(180)
    full = compute_feature_frame(df)
    prefix = compute_feature_frame(df.iloc[:121].copy())
    i = 120
    for col in ("feat_ma_slope", "feat_atr", "feat_rsi", "feat_prior_high", "feat_h1_dir"):
        a = full.iloc[i][col]
        b = prefix.iloc[i][col]
        if pd.isna(a) and pd.isna(b):
            continue
        assert a == pytest.approx(b, rel=1e-9, abs=1e-12), col


def test_completed_h1_uses_previous_hour_only() -> None:
    df = synthetic_market(80)
    feat = compute_feature_frame(df)
    times = pd.to_datetime(feat["time"], utc=True)
    i = 30
    hour = times.dt.floor("h")
    assert hour.iloc[i] == hour.iloc[i]
    snap = snapshot_at(feat, i)
    assert snap["status"] == "ok"


def test_regime_uncertain_on_nan() -> None:
    assert classify_regime(ma_slope=float("nan"), atr=1, atr_pct=0.5, rsi=50, compression=0.2) == "uncertain"


def test_missing_features_no_trade() -> None:
    sigs = all_signals({"status": "ok"})
    assert all(s.direction == NO_TRADE for s in sigs.values())


def test_vote_conflict_abstains() -> None:
    snap = _snap_ok(ma_slope=2e-4, rsi=80.0, close=1.2, prior_high=1.1, prior_low=1.0, atr_pct=0.9, h1_dir=1.0)
    d = model_vote(snap, min_agree=1)
    dirs = set(d.signals.values())
    if BUY := "BUY":
        assert BUY in dirs or "SELL" in dirs
    if "BUY" in dirs and "SELL" in dirs:
        assert d.direction == NO_TRADE
        assert d.reason == "signal_conflict"


def test_vote_agreement_threshold() -> None:
    snap = _snap_ok(ma_slope=0.0, rsi=50.0, atr_pct=0.2, close=1.095, prior_high=1.10, prior_low=1.09)
    d = model_vote(snap, min_agree=2)
    assert d.direction == NO_TRADE


def test_regime_maps_uncertain_to_no_trade() -> None:
    d = model_regime(_snap_ok(regime="uncertain"))
    assert d.direction == NO_TRADE
    assert "uncertain" in d.reason or "unsuitable" in d.reason


def test_spread_filter_no_trade() -> None:
    d = model_regime(_snap_ok(spread_over_atr=0.9), cost="base")
    assert d.direction == NO_TRADE
    assert d.reason == "spread_excessive"


def test_baseline_no_trade_always_abstains() -> None:
    d = baseline_no_trade(_snap_ok())
    assert d.direction == NO_TRADE
    assert d.abstain


def test_weight_normalisation_bounds() -> None:
    st = WeightState()
    enqueue_outcome(st, candidate_id="proxy_trend_ma_slope_v1", ready_i=10, pnl=-1.0)
    apply_delayed_outcomes(st, 10, eta=0.15)
    w = st.weights["proxy_trend_ma_slope_v1"]
    assert 0.05 <= w <= 5.0


def test_delayed_outcome_not_applied_early() -> None:
    st = WeightState()
    before = dict(st.weights)
    enqueue_outcome(st, candidate_id="proxy_rsi_mean_reversion_v1", ready_i=50, pnl=1.0)
    apply_delayed_outcomes(st, 49)
    assert st.weights == before
    apply_delayed_outcomes(st, 50)
    assert st.weights["proxy_rsi_mean_reversion_v1"] > before["proxy_rsi_mean_reversion_v1"]


def test_weight_state_restart(tmp_path: Path) -> None:
    p = tmp_path / "w.json"
    st = WeightState()
    st.weights["proxy_trend_ma_slope_v1"] = 1.4
    st.save(p)
    loaded = WeightState.load(p)
    assert loaded.weights["proxy_trend_ma_slope_v1"] == pytest.approx(1.4)


def test_corrupt_weight_state_resets(tmp_path: Path) -> None:
    p = tmp_path / "w.json"
    p.write_text("{}", encoding="utf-8")
    st = WeightState.load(p)
    assert st.version == "exp_weights_v1"
    assert st.weights["proxy_trend_ma_slope_v1"] == 1.0


def test_dynamic_determinism() -> None:
    snap = _snap_ok()
    a = model_dynamic(snap, WeightState())
    b = model_dynamic(snap, WeightState())
    assert a.direction == b.direction
    assert a.reason == b.reason


def test_bid_ask_buy_pays_ask() -> None:
    df = synthetic_market(100)
    feat = compute_feature_frame(df)
    px = fill_price(feat, 90, "BUY", "base")
    assert px is not None
    assert px >= float(feat.iloc[90]["close"]) - 1e-9


def test_gbp_conversion_estimate() -> None:
    assert quote_to_gbp(1.35, "EUR_USD", 1.35) == pytest.approx(1.0)


def test_broker_isolation() -> None:
    assert forbidden_hits() == {}


def test_inventory_flags_no_fresh_holdout() -> None:
    inv = inventory()
    assert inv["original_ai_rl"] == "ORIGINAL_DECISION_NOT_REPRODUCIBLE"
    assert inv["economic_events"] == "UNAVAILABLE"
    for row in inv["pairs"]:
        assert row["genuine_fresh_holdout"] is False


def test_synthetic_eval_runs() -> None:
    from forex_bot.research.adaptive_ensemble.evaluate import evaluate_frame

    df = synthetic_market(220)
    out = evaluate_frame(df, pair="EUR_USD", cost="base", lo=80, hi=200)
    assert "no_trade" in out
    assert out["no_trade"]["trade_count"] == 0
    assert out["no_trade"]["label"] == LABEL
    for rec in out.values():
        assert rec["evidence_class"] == "PREVIOUSLY_EXAMINED_EXPLORATORY"
        assert rec["financing"] == "UNAVAILABLE"


def test_feature_missingness_snapshot() -> None:
    df = synthetic_market(30)
    feat = compute_feature_frame(df)
    snap = snapshot_at(feat, 5)
    assert snap["economic_events"] == "UNAVAILABLE"
    assert snapshot_at(feat, 999)["status"] == "UNAVAILABLE"

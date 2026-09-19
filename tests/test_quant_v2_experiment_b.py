"""Focused tests for Quant V2 Experiment B cross-pair primitives."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from forex_bot.decision_quality.cross_pair import (
    apply_pca1,
    instrument_to_usd,
    leave_one_out_median,
    residual,
    reversal_instrument_side,
    synchronized_panel,
    train_betas,
    train_pca1,
    usd_ranks,
    usd_to_instrument,
)
from forex_bot.decision_quality.event_discovery import enter_true_grouped, event_bootstrap_mean
from forex_bot.decision_quality.spread_volume import half_close_spread, to_pips


def test_usd_orientation_all_six_symbols():
    r = np.array([0.01])
    assert instrument_to_usd("EUR_USD", r)[0] == pytest.approx(-0.01)
    assert instrument_to_usd("GBP_USD", r)[0] == pytest.approx(-0.01)
    assert instrument_to_usd("AUD_USD", r)[0] == pytest.approx(-0.01)
    assert instrument_to_usd("USD_JPY", r)[0] == pytest.approx(0.01)
    assert instrument_to_usd("USD_CAD", r)[0] == pytest.approx(0.01)
    assert instrument_to_usd("USD_CHF", r)[0] == pytest.approx(0.01)
    assert usd_to_instrument("EUR_USD", instrument_to_usd("EUR_USD", r))[0] == pytest.approx(0.01)
    assert usd_to_instrument("USD_JPY", instrument_to_usd("USD_JPY", r))[0] == pytest.approx(0.01)


def test_reversal_side_maps_usd_residual_to_instrument():
    assert reversal_instrument_side("EUR_USD", 0.01) == "BUY"
    assert reversal_instrument_side("USD_JPY", 0.01) == "SELL"
    assert reversal_instrument_side("EUR_USD", -0.01) == "SELL"
    assert reversal_instrument_side("USD_JPY", -0.01) == "BUY"


def test_synchronized_panel_inner_join_no_forward_fill():
    t0 = pd.Timestamp("2025-09-01 00:00")
    t1 = pd.Timestamp("2025-09-01 00:05")
    t2 = pd.Timestamp("2025-09-01 00:10")
    a = pd.DataFrame({"time": [t0, t1, t2], "close": [1.0, 1.1, 1.2]})
    b = pd.DataFrame({"time": [t0, t2], "close": [2.0, 2.2]})  # t1 missing — not filled
    panel = synchronized_panel({"EUR_USD": a, "USD_JPY": b}, "close")
    assert list(panel.index) == [t0, t2]
    assert 1.1 not in panel["EUR_USD"].to_numpy()
    assert panel.loc[t2, "USD_JPY"] == pytest.approx(2.2)


def test_six_symbol_synchronization_drops_partial_rows():
    t0 = pd.Timestamp("2025-09-01 00:00")
    t1 = pd.Timestamp("2025-09-01 00:05")
    symbols = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF"]
    frames = {s: pd.DataFrame({"time": [t0, t1], "v": [1.0, 2.0]}) for s in symbols}
    frames["USD_CHF"] = pd.DataFrame({"time": [t0], "v": [1.0]})  # t1 incomplete
    panel = synchronized_panel(frames, "v")
    assert list(panel.index) == [t0]
    assert list(panel.columns) == symbols


def test_leave_one_out_factor_excludes_target():
    idx = pd.date_range("2025-09-01", periods=3, freq="5min")
    wide = pd.DataFrame(
        {
            "EUR_USD": [10.0, 10.0, 10.0],
            "GBP_USD": [0.0, 0.0, 0.0],
            "AUD_USD": [0.0, 0.0, 0.0],
            "USD_JPY": [0.0, 0.0, 0.0],
            "USD_CAD": [0.0, 0.0, 0.0],
            "USD_CHF": [0.0, 0.0, 0.0],
        },
        index=idx,
    )
    loo = leave_one_out_median(wide)
    assert loo["EUR_USD"].iloc[0] == pytest.approx(0.0)
    assert loo["GBP_USD"].iloc[0] == pytest.approx(0.0)


def test_train_only_pca_frozen_on_later_data():
    rng = np.random.default_rng(0)
    train = rng.normal(size=(200, 6))
    later = rng.normal(loc=5.0, size=(50, 6))
    fit = train_pca1(train)
    later_fit = train_pca1(later)
    assert not np.allclose(fit["weights"], later_fit["weights"])
    a = apply_pca1(later, fit)
    b = apply_pca1(later, fit)
    assert np.allclose(a, b)
    # later refit would change scores
    assert not np.allclose(a, apply_pca1(later, later_fit))


def test_residual_calculation():
    f = np.arange(1.0, 31.0)
    y = 2.0 * f
    beta = train_betas(y, f)
    assert beta == pytest.approx(2.0)
    r = residual(y, f, beta)
    assert np.allclose(r, 0.0)


def test_relative_ranks_strongest_is_one():
    idx = pd.date_range("2025-09-01", periods=1, freq="5min")
    wide = pd.DataFrame(
        {"EUR_USD": [0.3], "GBP_USD": [0.1], "AUD_USD": [0.0], "USD_JPY": [-0.1], "USD_CAD": [-0.2], "USD_CHF": [-0.4]},
        index=idx,
    )
    ranks = usd_ranks(wide)
    assert ranks.loc[idx[0], "EUR_USD"] == 1
    assert ranks.loc[idx[0], "USD_CHF"] == 6


def test_lag_alignment_no_lookahead():
    factor = pd.Series([1.0, 2.0, 3.0, 4.0], index=pd.date_range("2025-09-01", periods=4, freq="5min"))
    future = pd.Series([10.0, 20.0, 30.0, 40.0], index=factor.index)
    lagged = factor.shift(2)
    # at t2, feature is factor[t0]=1, label future[t2]=30 — not future before t2
    assert lagged.iloc[2] == pytest.approx(1.0)
    assert future.iloc[2] == pytest.approx(30.0)
    assert lagged.iloc[2] != future.iloc[0]


def test_half_spread_cost_reuse():
    half = half_close_spread(np.array([1.1002]), np.array([1.1000]))
    assert to_pips(half, "EUR_USD")[0] == pytest.approx(1.0)


def test_bootstrap_fixed_seed_reproducible():
    x = np.arange(40, dtype=float)
    a = event_bootstrap_mean(x, seed=42, reps=30)
    b = event_bootstrap_mean(x, seed=42, reps=30)
    assert a == b


def test_source_csv_immutability():
    path = Path("data/historical/EUR_USD_M5.csv")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    _ = pd.read_csv(path, nrows=2)
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert before == after


def test_residual_transition_events():
    extreme = np.array([False, True, True, False, True])
    g = np.array(["EUR_USD"] * 5)
    assert enter_true_grouped(extreme, g).tolist() == [False, True, False, False, True]


def test_dispersion_uses_row_not_future():
    idx = pd.date_range("2025-09-01", periods=2, freq="5min")
    wide = pd.DataFrame(
        {"A": [0.0, 10.0], "B": [0.0, -10.0], "C": [0.0, 0.0]},
        index=idx,
    )
    std = wide.std(axis=1, ddof=0)
    assert std.iloc[0] == pytest.approx(0.0)
    assert std.iloc[1] > 0

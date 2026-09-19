"""Focused tests for event / opportunity discovery primitives."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from forex_bot.decision_quality.event_discovery import (
    BOOT_SEED,
    USD_QUOTE,
    enter_true,
    enter_true_grouped,
    event_bootstrap_mean,
    future_path_block,
    half_spread_pips,
    other_pairs_usd_context,
    path_order,
    prior_rolling_extrema,
    usd_direction_return,
)


def test_enter_true_counts_transition_not_persistence():
    flag = np.array([False, True, True, True, False, True])
    got = enter_true(flag)
    assert got.tolist() == [False, True, False, False, False, True]


def test_enter_true_grouped_resets_at_symbol_boundary():
    flag = np.array([True, True, True, True])
    group = np.array(["EUR_USD", "EUR_USD", "GBP_USD", "GBP_USD"])
    got = enter_true_grouped(flag, group)
    assert got.tolist() == [True, False, True, False]


def test_prior_rolling_high_excludes_current_bar():
    high = np.array([1.0, 3.0, 2.0, 5.0, 4.0])
    prior = prior_rolling_extrema(high, 2, "max")
    # index 3 uses bars 1 and 2 only (3.0, 2.0) — not current 5.0
    assert prior[3] == pytest.approx(3.0)
    assert prior[4] == pytest.approx(5.0)
    assert np.isnan(prior[0])
    assert np.isnan(prior[1])


def test_prior_rolling_low_excludes_current_bar():
    low = np.array([5.0, 1.0, 2.0, 0.5, 3.0])
    prior = prior_rolling_extrema(low, 2, "min")
    assert prior[3] == pytest.approx(1.0)
    assert prior[4] == pytest.approx(0.5)


def test_future_path_uses_subsequent_bars_only():
    close = np.array([10.0, 11.0, 9.0, 12.0, 8.0])
    high = np.array([10.5, 11.5, 9.5, 12.5, 8.5])
    low = np.array([9.5, 10.5, 8.5, 11.5, 7.5])
    blk = future_path_block(close, high, low, 2)
    # bar 0 future is bars 1-2
    assert blk["fwd_high"][0] == pytest.approx(11.5)
    assert blk["fwd_low"][0] == pytest.approx(8.5)
    assert blk["fwd_close"][0] == pytest.approx(9.0)
    assert blk["bars_to_high"][0] == 1
    assert blk["bars_to_low"][0] == 2
    # bar 3 future is bar 4 + pad — incomplete last close
    assert not blk["complete"][3] or np.isnan(blk["fwd_close"][4])


def test_mfe_up_down_from_current_close():
    close = np.array([1.0000, 1.0010, 0.9990])
    high = np.array([1.0002, 1.0020, 1.0000])
    low = np.array([0.9998, 0.9995, 0.9980])
    blk = future_path_block(close, high, low, 2)
    pip = 0.0001
    mfe_up = (blk["fwd_high"][0] - close[0]) / pip
    mfe_dn = (close[0] - blk["fwd_low"][0]) / pip
    assert mfe_up == pytest.approx(20.0)
    assert mfe_dn == pytest.approx(20.0)


def test_path_order_up_first():
    close = np.array([1.0, 1.0, 1.0])
    wh = np.array([[1.2, 1.3], [np.nan, np.nan], [np.nan, np.nan]])
    wl = np.array([[0.95, 0.7], [np.nan, np.nan], [np.nan, np.nan]])
    labels = path_order(close, wh, wl, np.array([0.15, 0.15, 0.15]))
    assert labels[0] == "UP_FIRST"


def test_path_order_down_first():
    close = np.array([1.0])
    wh = np.array([[1.05, 1.4]])
    wl = np.array([[0.8, 0.7]])
    labels = path_order(close, wh, wl, np.array([0.15]))
    assert labels[0] == "DOWN_FIRST"


def test_path_order_neither():
    close = np.array([1.0])
    wh = np.array([[1.01, 1.02]])
    wl = np.array([[0.99, 0.98]])
    labels = path_order(close, wh, wl, np.array([0.10]))
    assert labels[0] == "NEITHER"


def test_path_order_same_bar_is_ambiguous():
    close = np.array([1.0])
    wh = np.array([[1.2, 1.3]])
    wl = np.array([[0.8, 0.7]])
    labels = path_order(close, wh, wl, np.array([0.15]))
    assert labels[0] == "AMBIGUOUS"


def test_cost_hurdle_uses_modeled_half_spread():
    assert half_spread_pips("EUR_USD") == pytest.approx(1.0)
    assert half_spread_pips("GBP_USD") == pytest.approx(1.5)
    assert half_spread_pips("USD_JPY") == pytest.approx(1.0)


def test_usd_orientation_quote_vs_base():
    assert usd_direction_return("EUR_USD", np.array([0.01]))[0] == pytest.approx(-0.01)
    assert usd_direction_return("GBP_USD", np.array([0.01]))[0] == pytest.approx(-0.01)
    assert usd_direction_return("AUD_USD", np.array([0.01]))[0] == pytest.approx(-0.01)
    assert usd_direction_return("USD_JPY", np.array([0.01]))[0] == pytest.approx(0.01)
    assert usd_direction_return("USD_CAD", np.array([0.01]))[0] == pytest.approx(0.01)
    assert usd_direction_return("USD_CHF", np.array([0.01]))[0] == pytest.approx(0.01)
    for s in USD_QUOTE:
        assert usd_direction_return(s, np.array([-0.02]))[0] == pytest.approx(0.02)


def test_other_pairs_context_excludes_self():
    times = pd.to_datetime(["2025-09-01 00:00"] * 6)
    symbols = pd.Series(["EUR_USD", "GBP_USD", "AUD_USD", "USD_JPY", "USD_CAD", "USD_CHF"])
    ret = pd.Series([0.01, 0.00, 0.00, 0.00, 0.00, 0.00])
    ctx = other_pairs_usd_context(times, symbols, ret)
    eur = ctx.loc[ctx["symbol"] == "EUR_USD"].iloc[0]
    # EUR own USD dir is -0.01; others are all 0 so median 0; self not in others
    assert eur["usd_own"] == pytest.approx(-0.01)
    assert eur["usd_others_med"] == pytest.approx(0.0)


def test_usd_context_requires_aligned_completed_times():
    times = pd.to_datetime(
        ["2025-09-01 00:00", "2025-09-01 00:00", "2025-09-01 00:05", "2025-09-01 00:05"]
    )
    symbols = pd.Series(["EUR_USD", "USD_JPY", "EUR_USD", "USD_JPY"])
    ret = pd.Series([0.01, 0.02, 0.03, 0.04])
    ctx = other_pairs_usd_context(times, symbols, ret)
    row = ctx.loc[(ctx["symbol"] == "EUR_USD") & (ctx["time"] == pd.Timestamp("2025-09-01 00:00"))].iloc[0]
    # only USD_JPY is the other pair at that stamp; its USD dir is +0.02
    assert row["usd_others_med"] == pytest.approx(0.02)


def test_future_windows_are_chronological_no_lookahead():
    close = np.arange(6, dtype=float)
    high = close + 0.1
    low = close - 0.1
    blk = future_path_block(close, high, low, 2)
    # future high at i=2 is max of bars 3,4 = 4.1, never uses bar 2
    assert blk["fwd_high"][2] == pytest.approx(4.1)
    assert blk["fwd_close"][2] == pytest.approx(4.0)


def test_event_independence_one_count_per_run():
    flag = np.array([True] * 20)
    assert int(enter_true(flag).sum()) == 1


def test_bootstrap_fixed_seed_reproducible():
    rng = np.random.default_rng(0)
    x = rng.normal(size=80)
    a = event_bootstrap_mean(x, seed=BOOT_SEED, reps=50)
    b = event_bootstrap_mean(x, seed=BOOT_SEED, reps=50)
    assert a["mean"] == b["mean"]
    assert a["ci05"] == b["ci05"]
    assert a["ci95"] == b["ci95"]
    assert a["seed"] == 42

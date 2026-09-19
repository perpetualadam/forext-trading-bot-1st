"""Focused tests for Quant V2 Experiment A spread/volume primitives."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from forex_bot.decision_quality.event_discovery import enter_true_grouped
from forex_bot.decision_quality.spread_volume import (
    apply_frozen_edges,
    assign_quintile,
    flag_invalid_spread,
    full_close_spread,
    half_close_spread,
    lagged_rolling_median,
    modeled_half_spread_pips,
    modeled_half_spread_price,
    to_pips,
    train_quantile_edges,
    two_sided_hurdle,
)
from forex_bot.profit_protection import pip_size


def test_full_vs_half_spread_semantics():
    ask = np.array([1.10020])
    bid = np.array([1.10000])
    full = full_close_spread(ask, bid)
    half = half_close_spread(ask, bid)
    assert full[0] == pytest.approx(0.00020)
    assert half[0] == pytest.approx(0.00010)
    # V1 modeled entry cost is HALF-spread, not full spread
    assert modeled_half_spread_price("EUR_USD") == pytest.approx(0.0001)
    assert modeled_half_spread_pips("EUR_USD") == pytest.approx(1.0)
    assert modeled_half_spread_pips("GBP_USD") == pytest.approx(1.5)


def test_jpy_pip_conversion():
    assert pip_size("USD_JPY") == pytest.approx(0.01)
    full = full_close_spread(np.array([150.02]), np.array([150.00]))
    assert to_pips(full, "USD_JPY")[0] == pytest.approx(2.0)
    assert to_pips(full / 2.0, "USD_JPY")[0] == pytest.approx(1.0)
    assert to_pips(np.array([0.00020]), "EUR_USD")[0] == pytest.approx(2.0)


def test_negative_spread_not_silently_cleaned():
    full = full_close_spread(np.array([1.10, 1.09, np.nan]), np.array([1.10, 1.10, 1.10]))
    flags = flag_invalid_spread(full)
    assert flags["zero"][0]
    assert flags["negative"][1]
    assert flags["missing"][2]
    # original values remain
    assert full[1] < 0


def test_train_only_bucket_boundaries_frozen_later():
    rng = np.random.default_rng(0)
    train = rng.normal(1.0, 0.1, size=500)
    later = rng.normal(3.0, 0.1, size=200)
    edges = train_quantile_edges(train)
    later_edges = train_quantile_edges(later)
    # later distribution is shifted; frozen edges must still be the TRAIN ones
    q_later_with_train = assign_quintile(later, edges)
    q_later_if_refit = assign_quintile(later, later_edges)
    assert not np.array_equal(edges, later_edges)
    assert q_later_with_train.min() >= 5  # all later values sit in TRAIN q5
    assert apply_frozen_edges(later, edges).tolist() == q_later_with_train.tolist()
    assert q_later_if_refit.mean() != q_later_with_train.mean()


def test_volume_normalization_uses_lagged_baseline():
    vol = np.array([10.0, 10.0, 10.0, 40.0, 10.0])
    g = np.array(["EUR_USD"] * 5)
    med = lagged_rolling_median(vol, 3, g)
    assert np.isnan(med[0])
    assert np.isnan(med[2])  # not enough lagged bars
    assert med[3] == pytest.approx(10.0)  # previous 3 are 10,10,10 — excludes 40
    assert med[4] == pytest.approx(10.0)


def test_event_transition_not_persistent_state():
    high = np.array([False, True, True, True, False, True])
    g = np.array(["A"] * 6)
    ev = enter_true_grouped(high, g)
    assert ev.tolist() == [False, True, False, False, False, True]


def test_cost_normalized_future_movement():
    mfe_up = np.array([2.0, 0.5])
    cost = np.array([1.0, 1.0])
    ratio = mfe_up / cost
    assert ratio[0] == pytest.approx(2.0)
    assert ratio[1] == pytest.approx(0.5)


def test_two_sided_contemporaneous_hurdle_labels():
    up = np.array([2.0, 2.0, 0.5, 0.5, np.nan])
    dn = np.array([2.0, 0.5, 2.0, 0.5, 1.0])
    cost = np.array([1.0, 1.0, 1.0, 1.0, 1.0])
    lab = two_sided_hurdle(up, dn, cost)
    assert lab.tolist() == ["BOTH", "UP_ONLY", "DOWN_ONLY", "NEITHER", "INVALID"]


def test_no_lookahead_in_lagged_median_across_symbols():
    vol = np.array([5.0, 50.0, 5.0, 50.0])
    g = np.array(["EUR_USD", "EUR_USD", "GBP_USD", "GBP_USD"])
    med = lagged_rolling_median(vol, 1, g)
    assert med[1] == pytest.approx(5.0)
    assert np.isnan(med[2])  # new symbol, no prior
    assert med[3] == pytest.approx(5.0)


def test_source_csv_immutability():
    path = Path("data/historical/EUR_USD_M5.csv")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    raw = pd.read_csv(path, nrows=3)
    _ = full_close_spread(raw["ask_close"].to_numpy(), raw["bid_close"].to_numpy())
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert before == after

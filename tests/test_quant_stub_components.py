"""Research-only tests for SMA-state / momentum-sign components. No production change."""

from __future__ import annotations

import numpy as np
import pandas as pd

from forex_bot.decision_quality.stub_components import (
    AGE_BUCKET_NAMES,
    age_bucket,
    bars_since_last_cross,
    current_stub_allow,
    first_qualifying_in_episode,
    episode_ids,
    momentum_sign,
    signed_forward_pips,
    sma_state,
)


def test_sma_state_matches_stub_orientation():
    fast = np.array([1.102, 1.100, 1.1000000005])
    slow = np.array([1.100, 1.102, 1.1000000000])
    assert list(sma_state(fast, slow)) == [1, -1, 0]


def test_bars_since_last_cross_zero_on_event_then_increments():
    state = np.array([0, 1, 1, 1, -1, -1, 0, 1], dtype=np.int8)
    age = bars_since_last_cross(state)
    assert np.isnan(age[0])
    assert age[1] == 0
    assert age[2] == 1
    assert age[3] == 2
    assert age[4] == 0
    assert age[5] == 1
    assert np.isnan(age[6])
    assert age[7] == 0


def test_predeclared_age_buckets():
    age = np.array([0, 1, 2, 3, 4, 6, 7, 12, 13, 24, 25, 100], dtype=float)
    buckets = list(age_bucket(age))
    assert buckets == ["0", "1", "2-3", "2-3", "4-6", "4-6", "7-12", "7-12", "13-24", "13-24", "25+", "25+"]
    assert AGE_BUCKET_NAMES == ("0", "1", "2-3", "4-6", "7-12", "13-24", "25+")


def test_momentum_agree_oppose_does_not_use_magnitude_name_as_side():
    state = np.array([1, 1, -1, -1], dtype=np.int8)
    mom = momentum_sign(np.array([0.0002, -0.0002, -0.0002, 0.0002]))
    agree = (state == mom)
    assert list(agree) == [True, False, True, False]


def test_first_qualifying_is_once_per_episode():
    ep = np.array([0, 0, 0, 1, 1])
    qual = np.array([False, True, True, True, True])
    first = first_qualifying_in_episode(ep, qual)
    assert list(first) == [False, True, False, True, False]


def test_current_stub_allow_ignores_momentum_sign():
    state = np.array([1, 1, 1, 0], dtype=np.int8)
    ret = np.array([0.0002, -0.0002, 0.00005, 0.0002])
    atr = np.array([0.001, 0.001, 0.001, 0.001])
    allow = current_stub_allow(state, ret, atr)
    assert list(allow) == [True, True, False, False]


def test_inverse_signed_forward_is_negation():
    close = np.array([1.1000, 1.1005, 1.1010, 1.1002])
    buy = np.array([1, 1, 1, 1], dtype=np.int8)
    sell = -buy
    fwd_buy = signed_forward_pips("EUR_USD", buy, close, 1)
    fwd_sell = signed_forward_pips("EUR_USD", sell, close, 1)
    both = np.isfinite(fwd_buy) & np.isfinite(fwd_sell)
    assert np.allclose(fwd_buy[both], -fwd_sell[both])


def test_episode_ids_split_on_flip():
    state = np.array([1, 1, -1, -1, 0, 1], dtype=np.int8)
    assert list(episode_ids(state)) == [0, 0, 1, 1, -1, 2]

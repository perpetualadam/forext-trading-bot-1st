"""Observability-only silent-skip diagnostics.

R.34 retired the operational quant stub. Historical directional expectations are
obsolete. The live function abstains and must not reach sizing.
"""

from __future__ import annotations

import logging

import pytest

from forex_bot.ai_ensemble import _quant_stub_vote
from forex_bot.decision_skip_log import (
    NO_STRATEGY_SELECTED,
    QUANT_SIGNAL_PASS,
    STRATEGY_INACTIVE,
    log_strategy_pre_sizing_skip,
    strategy_pool_snapshot,
)
from forex_bot.strategy_meta import allocate, meta, select_strategy_legacy, strategies


def _payload(**overrides):
    base = {
        "symbol": "EUR_USD",
        "timeframe": "M5",
        "m5_bar_time": "2026-10-01T12:00:00Z",
        "price": 1.1000,
        "ma_fast": 1.1010,
        "ma_slow": 1.0990,
        "returns": 0.0005,
        "atr": 0.0008,
        "strategy": "trend",
    }
    base.update(overrides)
    return base


def _decision(vote: dict) -> tuple:
    return (vote.get("allow"), vote.get("direction"), vote.get("confidence"))


def _messages(caplog) -> str:
    return "\n".join(caplog.messages)


@pytest.fixture
def restore_strategy_state():
    before_ids = {name: id(strat) for name, strat in strategies.items()}
    before_active = {name: strat.active for name, strat in strategies.items()}
    before_pnl = {name: list(strat.pnl) for name, strat in strategies.items()}
    before_meta = {name: list(scores) for name, scores in meta.scores.items()}
    yield
    for name, strat in strategies.items():
        assert id(strat) == before_ids[name]
        strat.active = before_active[name]
        strat.pnl[:] = before_pnl[name]
    meta.scores.clear()
    meta.scores.update({name: list(scores) for name, scores in before_meta.items()})
    assert {name: id(strat) for name, strat in strategies.items()} == before_ids
    assert {name: strat.active for name, strat in strategies.items()} == before_active
    assert {name: list(strat.pnl) for name, strat in strategies.items()} == before_pnl


def _assert_retired(vote: dict) -> None:
    assert vote["allow"] is False
    assert vote["direction"] is None
    assert vote["status"] == "unavailable"
    assert vote["reason"] == "quant_stub_removed"


def test_retired_stub_abstains_for_former_buy_and_sell_payloads(caplog):
    with caplog.at_level(logging.INFO, logger="forex_bot.decision_skip_log"):
        buy = _quant_stub_vote(_payload(ma_fast=1.1010, ma_slow=1.0990, returns=0.0005, atr=0.0008))
        sell = _quant_stub_vote(_payload(ma_fast=1.0990, ma_slow=1.1010, returns=-0.0005, atr=0.0008))
    _assert_retired(buy)
    _assert_retired(sell)
    assert QUANT_SIGNAL_PASS not in _messages(caplog)


def test_retired_stub_abstains_for_former_boundary_cases():
    payloads = [
        dict(ma_fast=1.1000, ma_slow=1.1000, returns=0.001, atr=0.001),
        dict(returns=0.00005, atr=0.001),
        dict(returns=0.0001, atr=0.001),
        dict(returns=0.0001000001, atr=0.001),
        dict(returns=0.001, atr=0.0),
        dict(ma_fast=float("nan"), ma_slow=1.1, returns=0.001, atr=0.001),
        dict(ma_fast="x", ma_slow="y", sma_fast="x", sma_slow="y"),
        dict(returns=0.0004, atr=0.001),
        dict(returns=0.002, atr=0.001),
    ]
    for item in payloads:
        _assert_retired(_quant_stub_vote(_payload(**item)))


def test_logging_does_not_mutate_strategy_objects(restore_strategy_state, caplog):
    ids_before = {name: id(strat) for name, strat in strategies.items()}
    pnl_before = {name: list(strat.pnl) for name, strat in strategies.items()}
    active_before = {name: strat.active for name, strat in strategies.items()}
    with caplog.at_level(logging.INFO, logger="forex_bot.decision_skip_log"):
        _quant_stub_vote(_payload())
        log_strategy_pre_sizing_skip(
            symbol="EUR_USD",
            reason=NO_STRATEGY_SELECTED,
            selected=None,
            lookback=50,
            horizon="legacy",
        )
        strategy_pool_snapshot()
    assert {name: id(strat) for name, strat in strategies.items()} == ids_before
    assert {name: list(strat.pnl) for name, strat in strategies.items()} == pnl_before
    assert {name: strat.active for name, strat in strategies.items()} == active_before


def test_no_strategy_selected_path_and_inactive_log(restore_strategy_state, caplog):
    for strat in strategies.values():
        strat.active = False
    assert allocate() == {}
    assert select_strategy_legacy() is None
    with caplog.at_level(logging.INFO, logger="forex_bot.decision_skip_log"):
        log_strategy_pre_sizing_skip(
            symbol="GBP_USD",
            reason=NO_STRATEGY_SELECTED,
            selected=None,
            lookback=50,
            horizon="legacy",
        )
        name = next(iter(strategies))
        strategies[name].active = False
        log_strategy_pre_sizing_skip(
            symbol="GBP_USD",
            reason=STRATEGY_INACTIVE,
            selected=name,
            lookback=50,
            horizon="legacy",
        )
    text = _messages(caplog)
    assert NO_STRATEGY_SELECTED in text
    assert STRATEGY_INACTIVE in text
    assert "pair=GBP_USD" in text
    assert "selected=n/a" in text or "selected=None" in text or "selected=%s" % name in text


def test_selected_strategy_still_returned_when_active(restore_strategy_state):
    for strat in strategies.values():
        strat.active = True
        strat.pnl.clear()
    name = select_strategy_legacy()
    assert name in strategies
    assert strategies[name].active is True


def test_obsolete_evaluate_patches_are_retired():
    """The old evaluate() monkeypatches targeted fetch_ohlcv on bot_loop.

    That attribute is gone. Replaying evaluate() here would call the live
    candle path. Shared-path sizing remains covered by the R.34 fail-closed tests.
    """
    import forex_bot.bot_loop as bot_loop

    assert not hasattr(bot_loop, "fetch_ohlcv")
    _assert_retired(_quant_stub_vote(_payload()))

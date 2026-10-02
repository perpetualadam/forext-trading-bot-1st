"""Observability-only silent-skip diagnostics. Decisions must stay identical."""

from __future__ import annotations

import logging
import math
import pandas as pd
import pytest

from forex_bot.ai_ensemble import _quant_stub_vote
from forex_bot.decision_skip_log import (
    NO_STRATEGY_SELECTED,
    QUANT_ATR_NOT_OK,
    QUANT_M5_MOVE_BELOW_THRESHOLD,
    QUANT_MA_INVALID,
    QUANT_MA_NAN,
    QUANT_MA_NOT_CLEAR,
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


def test_quant_buy_pass_reason(caplog):
    with caplog.at_level(logging.INFO, logger="forex_bot.decision_skip_log"):
        v = _quant_stub_vote(_payload(ma_fast=1.1010, ma_slow=1.0990, returns=0.0005, atr=0.0008))
    assert _decision(v) == (True, "BUY", v["confidence"])
    assert 0.0 < v["confidence"] <= 1.0
    text = _messages(caplog)
    assert QUANT_SIGNAL_PASS in text
    assert QUANT_MA_NOT_CLEAR not in text
    assert QUANT_M5_MOVE_BELOW_THRESHOLD not in text
    assert "pair=EUR_USD" in text
    assert "direction=BUY" in text


def test_quant_sell_pass_reason(caplog):
    with caplog.at_level(logging.INFO, logger="forex_bot.decision_skip_log"):
        v = _quant_stub_vote(_payload(ma_fast=1.0990, ma_slow=1.1010, returns=-0.0005, atr=0.0008))
    assert v["allow"] is True
    assert v["direction"] == "SELL"
    assert QUANT_SIGNAL_PASS in _messages(caplog)
    assert QUANT_MA_NOT_CLEAR not in _messages(caplog)


def test_quant_unclear_ma_reason(caplog):
    with caplog.at_level(logging.INFO, logger="forex_bot.decision_skip_log"):
        v = _quant_stub_vote(_payload(ma_fast=1.1000, ma_slow=1.1000, returns=0.001, atr=0.001))
    assert v == {"allow": False, "confidence": 0.0, "direction": None}
    text = _messages(caplog)
    assert QUANT_MA_NOT_CLEAR in text
    assert QUANT_SIGNAL_PASS not in text
    assert QUANT_M5_MOVE_BELOW_THRESHOLD not in text


def test_quant_m5_below_threshold_and_exact_boundary(caplog):
    with caplog.at_level(logging.INFO, logger="forex_bot.decision_skip_log"):
        below = _quant_stub_vote(_payload(returns=0.00005, atr=0.001))
        boundary = _quant_stub_vote(_payload(returns=0.0001, atr=0.001))
        just_over = _quant_stub_vote(_payload(returns=0.0001000001, atr=0.001))
    assert below["allow"] is False and below["direction"] == "BUY"
    assert boundary["allow"] is False and boundary["direction"] == "BUY"
    assert just_over["allow"] is True and just_over["direction"] == "BUY"
    text = _messages(caplog)
    assert text.count(QUANT_M5_MOVE_BELOW_THRESHOLD) == 2
    assert QUANT_SIGNAL_PASS in text
    assert QUANT_MA_NOT_CLEAR not in text


def test_quant_atr_zero_reason(caplog):
    with caplog.at_level(logging.INFO, logger="forex_bot.decision_skip_log"):
        v = _quant_stub_vote(_payload(returns=0.001, atr=0.0))
    assert v["allow"] is False
    assert v["direction"] == "BUY"
    text = _messages(caplog)
    assert QUANT_ATR_NOT_OK in text
    assert QUANT_SIGNAL_PASS not in text
    assert QUANT_M5_MOVE_BELOW_THRESHOLD not in text


def test_quant_nan_and_invalid_ma_reasons(caplog):
    with caplog.at_level(logging.INFO, logger="forex_bot.decision_skip_log"):
        nan_v = _quant_stub_vote(_payload(ma_fast=float("nan"), ma_slow=1.1, returns=0.001, atr=0.001))
        bad_v = _quant_stub_vote(_payload(ma_fast="x", ma_slow="y", sma_fast="x", sma_slow="y"))
    assert nan_v == {"allow": False, "confidence": 0.0, "direction": None}
    assert bad_v == {"allow": False, "confidence": 0.0, "direction": None}
    text = _messages(caplog)
    assert QUANT_MA_NAN in text
    assert QUANT_MA_INVALID in text
    assert QUANT_SIGNAL_PASS not in text


def test_quant_return_keys_remain_decision_only():
    v = _quant_stub_vote(_payload())
    assert set(v) == {"allow", "confidence", "direction"}


def test_quant_equivalence_matches_prior_mapping_cases():
    cases = [
        dict(ma_fast=1.1010, ma_slow=1.0990, returns=0.0005, atr=0.0008),
        dict(ma_fast=1.0990, ma_slow=1.1010, returns=-0.0005, atr=0.0008),
        dict(ma_fast=1.1000, ma_slow=1.1000, returns=0.001, atr=0.001),
        dict(ma_fast=1.1010, ma_slow=1.0990, returns=0.00005, atr=0.001),
        dict(ma_fast=1.1010, ma_slow=1.0990, returns=0.001, atr=0.0),
        dict(ma_fast=float("nan"), ma_slow=1.1, returns=0.001, atr=0.001),
        dict(ma_fast=1.102, ma_slow=1.100, returns=-0.0005, atr=0.001),
        dict(ma_fast=1.098, ma_slow=1.100, returns=0.0005, atr=0.001),
        dict(price=154.30, ma_fast=154.31, ma_slow=154.20, returns=0.0002, atr=0.04),
        dict(
            sma_fast=1.090,
            sma_slow=1.100,
            ma_fast=1.200,
            ma_slow=1.000,
            returns=-0.0004,
            atr=0.001,
        ),
    ]
    expected = [
        (True, "BUY"),
        (True, "SELL"),
        (False, None),
        (False, "BUY"),
        (False, "BUY"),
        (False, None),
        (True, "BUY"),
        (True, "SELL"),
        (True, "BUY"),
        (True, "SELL"),
    ]
    for kwargs, (allow, direction) in zip(cases, expected, strict=True):
        v = _quant_stub_vote(_payload(**kwargs))
        assert v["allow"] is allow
        assert v["direction"] == direction
        if allow:
            assert 0.0 < v["confidence"] <= 1.0
        if direction is None:
            assert v["confidence"] == 0.0


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


@pytest.mark.asyncio
async def test_evaluate_strategy_none_does_not_reach_sizing(monkeypatch, caplog, restore_strategy_state):
    from forex_bot.bot_loop import evaluate

    idx = pd.date_range("2026-10-01", periods=80, freq="5min", tz="UTC")
    close = pd.Series(1.10 + (pd.Series(range(80)) * 0.0001), index=idx)
    raw = pd.DataFrame(
        {
            "time": idx,
            "open": close,
            "high": close + 0.0002,
            "low": close - 0.0002,
            "close": close,
            "volume": 1.0,
        }
    )
    sized = {"n": 0}

    def _ohlcv(*_a, **_k):
        return raw

    def _size(*_a, **_k):
        sized["n"] += 1
        return 2.0

    monkeypatch.setattr("forex_bot.bot_loop.fetch_ohlcv", _ohlcv)
    monkeypatch.setattr("forex_bot.bot_loop.in_active_session", lambda *_a, **_k: True)
    monkeypatch.setattr("forex_bot.bot_loop.flatten_for_weekend", lambda: False)
    monkeypatch.setattr("forex_bot.bot_loop.get_position", lambda *_a, **_k: None)
    monkeypatch.setattr("forex_bot.broker_exit.broker_exit_open_blocked_reason", lambda *_a, **_k: None)
    monkeypatch.setattr("forex_bot.bot_loop.pre_trade_entry_blocked_reason", lambda: None)
    monkeypatch.setattr("forex_bot.bot_loop.select_strategy", lambda *_a, **_k: (None, 50, "legacy"))
    monkeypatch.setattr("forex_bot.bot_loop.position_sizing", _size)
    with caplog.at_level(logging.INFO, logger="forex_bot.decision_skip_log"):
        await evaluate("EUR_USD")
    assert sized["n"] == 0
    assert NO_STRATEGY_SELECTED in _messages(caplog)
    assert QUANT_SIGNAL_PASS not in _messages(caplog)


@pytest.mark.asyncio
async def test_evaluate_quant_reject_does_not_reach_sizing(monkeypatch, caplog, restore_strategy_state):
    from forex_bot.bot_loop import evaluate

    idx = pd.date_range("2026-10-01", periods=80, freq="5min", tz="UTC")
    close = pd.Series([1.1000] * 80, index=idx)
    raw = pd.DataFrame(
        {
            "time": idx,
            "open": close,
            "high": close + 0.0001,
            "low": close - 0.0001,
            "close": close,
            "volume": 1.0,
        }
    )
    sized = {"n": 0}

    def _ohlcv(*_a, **_k):
        return raw

    def _size(*_a, **_k):
        sized["n"] += 1
        return 2.0

    monkeypatch.setattr("forex_bot.bot_loop.fetch_ohlcv", _ohlcv)
    monkeypatch.setattr("forex_bot.bot_loop.in_active_session", lambda *_a, **_k: True)
    monkeypatch.setattr("forex_bot.bot_loop.flatten_for_weekend", lambda: False)
    monkeypatch.setattr("forex_bot.bot_loop.get_position", lambda *_a, **_k: None)
    monkeypatch.setattr("forex_bot.broker_exit.broker_exit_open_blocked_reason", lambda *_a, **_k: None)
    monkeypatch.setattr("forex_bot.bot_loop.pre_trade_entry_blocked_reason", lambda: None)
    monkeypatch.setattr("forex_bot.bot_loop.select_strategy", lambda *_a, **_k: ("trend", 50, "legacy"))
    monkeypatch.setattr("forex_bot.bot_loop.volatility_ok", lambda *_a, **_k: True)
    monkeypatch.setattr("forex_bot.bot_loop.position_sizing", _size)
    with caplog.at_level(logging.INFO, logger="forex_bot.decision_skip_log"):
        await evaluate("EUR_USD")
    assert sized["n"] == 0
    text = _messages(caplog)
    assert QUANT_SIGNAL_PASS not in text
    assert any(
        code in text
        for code in (QUANT_MA_NOT_CLEAR, QUANT_M5_MOVE_BELOW_THRESHOLD, QUANT_ATR_NOT_OK, QUANT_MA_NAN)
    )


@pytest.mark.asyncio
async def test_evaluate_quant_pass_reaches_sizing(monkeypatch, caplog, restore_strategy_state):
    from forex_bot.ai_ensemble import AIEnsemble, LocalLLM
    from forex_bot.bot_loop import evaluate
    from forex_bot.indicators import compute_indicators as real_indicators

    idx = pd.date_range("2026-10-01", periods=80, freq="5min", tz="UTC")
    values = [1.1000] * 79 + [1.1035]
    close = pd.Series(values, index=idx)
    raw = pd.DataFrame(
        {
            "time": idx,
            "open": close,
            "high": close + 0.0003,
            "low": close - 0.0001,
            "close": close,
            "volume": 1.0,
        }
    )
    sized = {"n": 0}

    def _ohlcv(*_a, **_k):
        return raw

    def _size(*_a, **_k):
        sized["n"] += 1
        return 0.0

    def _indicators(df, lookback=None, **kwargs):
        out = real_indicators(df, lookback=lookback, **kwargs)
        out = out.copy()
        out["ma_fast"] = 1.1020
        out["ma_slow"] = 1.1000
        out["atr"] = 0.0010
        out["trend"] = 0.0020
        out["volatility"] = 0.0010
        return out

    monkeypatch.setattr("forex_bot.bot_loop.fetch_ohlcv", _ohlcv)
    monkeypatch.setattr("forex_bot.bot_loop.in_active_session", lambda *_a, **_k: True)
    monkeypatch.setattr("forex_bot.bot_loop.flatten_for_weekend", lambda: False)
    monkeypatch.setattr("forex_bot.bot_loop.get_position", lambda *_a, **_k: None)
    monkeypatch.setattr("forex_bot.broker_exit.broker_exit_open_blocked_reason", lambda *_a, **_k: None)
    monkeypatch.setattr("forex_bot.bot_loop.pre_trade_entry_blocked_reason", lambda: None)
    monkeypatch.setattr("forex_bot.bot_loop.select_strategy", lambda *_a, **_k: ("trend", 50, "legacy"))
    monkeypatch.setattr("forex_bot.bot_loop.volatility_ok", lambda *_a, **_k: True)
    monkeypatch.setattr("forex_bot.bot_loop.compute_indicators", _indicators)
    monkeypatch.setattr("forex_bot.bot_loop.ai", AIEnsemble(local_llms=[LocalLLM()]))
    monkeypatch.setattr("forex_bot.bot_loop.rl_agent.decide", lambda *_a, **_k: "BUY")
    monkeypatch.setattr("forex_bot.bot_loop.position_sizing", _size)
    with caplog.at_level(logging.INFO, logger="forex_bot.decision_skip_log"):
        await evaluate("EUR_USD")
    text = _messages(caplog)
    assert QUANT_SIGNAL_PASS in text
    assert QUANT_MA_NOT_CLEAR not in text
    assert QUANT_M5_MOVE_BELOW_THRESHOLD not in text
    assert sized["n"] == 1


def test_quant_confidence_formula_unchanged():
    v = _quant_stub_vote(_payload(returns=0.0004, atr=0.001))
    assert math.isclose(v["confidence"], 0.4, rel_tol=0, abs_tol=1e-12)
    v2 = _quant_stub_vote(_payload(returns=0.002, atr=0.001))
    assert v2["confidence"] == 1.0

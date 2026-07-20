"""Regression tests for logic/feature fixes (sizing, sessions, reconcile, AI fail-closed, RL gate)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from forex_bot.positions import Position, close_position, open_position, positions
from forex_bot.portfolio_exposure import (
    approx_gross_usd_notional_for,
    approx_signed_usd_exposure,
)
from forex_bot.session_rules import fx_market_open_at, in_active_session_at
from forex_bot.trading import (
    calculate_pnl,
    position_sizing,
    stop_risk_account_ccy,
)


@pytest.fixture(autouse=True)
def _clear_positions():
    positions.clear()
    yield
    positions.clear()


def test_usd_jpy_position_sizing_uses_quote_conversion():
    # $100 risk, stop 0.20 JPY at 150 → risk/unit = 0.20/150 → units ≈ 75000
    units = position_sizing("USD_JPY", 150.0, 149.80, 10000.0, risk_pct=0.01)
    assert units == pytest.approx(75000.0, rel=1e-6)


def test_eur_usd_position_sizing_unchanged():
    # $100 risk, stop 0.0020 → units = 50000
    units = position_sizing("EUR_USD", 1.1000, 1.0980, 10000.0, risk_pct=0.01)
    assert units == pytest.approx(50000.0, rel=1e-6)


def test_usd_jpy_pnl_converted_to_account_usd():
    pos = Position(
        symbol="USD_JPY",
        direction="BUY",
        units=1000.0,
        entry_price=150.0,
        stop_loss=149.8,
        take_profit=150.4,
        open_time=0.0,
        strategy_name="trend",
        rl_state="s",
        execution_kind="simulated",
    )
    # +1.0 JPY * 1000 = 1000 JPY ≈ 1000/151 USD
    pnl = calculate_pnl(pos, 151.0)
    assert pnl == pytest.approx(1000.0 / 151.0, rel=1e-6)


def test_stop_risk_and_exposure_helpers_usd_jpy():
    risk = stop_risk_account_ccy("USD_JPY", 150.0, 0.20, 75000.0)
    assert risk == pytest.approx(100.0, rel=1e-6)
    assert approx_gross_usd_notional_for("USD_JPY", 1000.0, 150.0) == 1000.0
    assert approx_gross_usd_notional_for("EUR_USD", 1000.0, 1.1) == pytest.approx(1100.0)


def test_signed_usd_exposure_short_usd_on_eur_buy():
    open_position(
        Position(
            symbol="EUR_USD",
            direction="BUY",
            units=1000.0,
            entry_price=1.10,
            stop_loss=1.09,
            take_profit=1.12,
            open_time=0.0,
            strategy_name="trend",
            rl_state="s",
            execution_kind="simulated",
        )
    )
    # Long EUR / short USD
    assert approx_signed_usd_exposure() == pytest.approx(-1100.0)


def test_fx_weekend_closed():
    sat = datetime(2026, 7, 18, 12, 0, 0)  # Saturday
    sun_morning = datetime(2026, 7, 19, 12, 0, 0)
    sun_open = datetime(2026, 7, 19, 21, 0, 0)
    fri_open = datetime(2026, 7, 17, 15, 0, 0)
    fri_closed = datetime(2026, 7, 17, 22, 0, 0)
    assert fx_market_open_at(sat) is False
    assert fx_market_open_at(sun_morning) is False
    assert fx_market_open_at(sun_open) is True
    assert fx_market_open_at(fri_open) is True
    assert fx_market_open_at(fri_closed) is False
    assert in_active_session_at("EUR_USD", sat) is False


def test_ai_ensemble_fails_closed_when_no_votes():
    import asyncio
    from forex_bot.ai_ensemble import AIEnsemble

    ens = AIEnsemble(local_llms=[], external_llms=[])

    async def _run():
        return await ens.vote({"price": 1.0}, "EUR_USD")

    out = asyncio.run(_run())
    assert out["allow"] is False
    assert out["confidence"] == 0.0


def test_oanda_close_uses_reduce_only():
    from forex_bot import oanda_exec

    captured: dict = {}

    class FakeAPI:
        def request(self, r):
            captured["data"] = r.data
            return {
                "orderFillTransaction": {
                    "price": "1.10000",
                    "pl": "1.5",
                    "id": "1",
                }
            }

    with (
        patch.object(oanda_exec, "get_api", return_value=FakeAPI()),
        patch.object(oanda_exec, "_account_id", return_value="ACC"),
    ):
        pl, px = oanda_exec._place_market_order_sync("EUR_USD", 10.0, "BUY")
    assert pl == 1.5
    assert px == 1.1
    assert captured["data"]["order"]["positionFill"] == "REDUCE_ONLY"


def test_oanda_open_attaches_sl_tp():
    from forex_bot import oanda_exec

    captured: dict = {}

    class FakeAPI:
        def request(self, r):
            captured["data"] = r.data
            return {
                "orderFillTransaction": {
                    "price": "1.10000",
                    "units": "10",
                    "id": "9",
                    "pl": "",
                }
            }

    with (
        patch.object(oanda_exec, "get_api", return_value=FakeAPI()),
        patch.object(oanda_exec, "_account_id", return_value="ACC"),
    ):
        fp, uf, oid, _pl = oanda_exec._place_market_order_open_sync(
            "EUR_USD",
            10.0,
            "BUY",
            "cid-1",
            stop_loss=1.0980,
            take_profit=1.1040,
        )
    assert fp == 1.1
    assert uf == 10.0
    assert oid == "9"
    order = captured["data"]["order"]
    assert order["stopLossOnFill"]["price"] == "1.09800"
    assert order["takeProfitOnFill"]["price"] == "1.10400"


def test_window_paper_excluded_from_broker_mismatch():
    from forex_bot.reconciliation import _is_broker_backed_local

    sim = Position(
        symbol="EUR_USD",
        direction="BUY",
        units=1.0,
        entry_price=1.1,
        stop_loss=1.0,
        take_profit=1.2,
        open_time=0.0,
        strategy_name="trend",
        rl_state="s",
        execution_kind="window_paper",
    )
    live = Position(
        symbol="EUR_USD",
        direction="BUY",
        units=1.0,
        entry_price=1.1,
        stop_loss=1.0,
        take_profit=1.2,
        open_time=0.0,
        strategy_name="trend",
        rl_state="s",
        execution_kind="live",
    )
    assert _is_broker_backed_local(sim) is False
    assert _is_broker_backed_local(live) is True


def test_execute_trade_unknown_strategy_no_keyerror(monkeypatch):
    import asyncio
    from forex_bot import trading as trading_mod

    monkeypatch.setattr(trading_mod, "log_trade_pg", lambda *a, **k: None)
    monkeypatch.setattr(trading_mod.analytics, "log_trade", lambda pnl: None)
    monkeypatch.setattr(trading_mod, "update_equity", lambda pnl: None)
    monkeypatch.setattr(trading_mod, "alert", lambda msg: None)

    async def _run():
        return await trading_mod.execute_trade(
            "EUR_USD",
            "reconcile_import",
            "BUY",
            10.0,
            1.1,
            1.09,
            1.12,
            realized_pnl=1.25,
            execution_kind="reconcile_import",
            exit_price=1.101,
        )

    pnl = asyncio.run(_run())
    assert pnl == 1.25


def test_fetch_broker_raises_in_broker_mode(monkeypatch):
    from forex_bot.execution import ExecutionMode
    from forex_bot import reconciliation as reco

    monkeypatch.setattr(reco, "get_api", lambda: None)
    with (
        patch("forex_bot.execution.get_execution_mode", return_value=ExecutionMode.LIVE_BROKER),
        pytest.raises(RuntimeError, match="unavailable"),
    ):
        reco.fetch_broker_positions_detail()

"""Paper/window_paper must never reach the broker; live identity stays distinct."""

from __future__ import annotations

import asyncio

import pytest

from forex_bot.execution import is_broker_backed, is_paper_like, is_paper_like_kind, open_fill_path
from forex_bot.oanda_exec import assert_broker_order_allowed, execute_oanda_market_open
from forex_bot.orders import orders_by_client_id, try_begin_order_submission
from forex_bot.positions import Position, import_position_from_broker, open_position, positions
from forex_bot.reconciliation import _is_broker_backed_local


def _pos(symbol: str, *, kind: str, direction: str = "SELL") -> Position:
    return Position(
        symbol=symbol,
        direction=direction,
        units=2.0,
        entry_price=1.15398,
        stop_loss=1.15468,
        take_profit=1.15259,
        open_time=0.0,
        strategy_name="trend",
        rl_state="s",
        execution_kind=kind,
        client_order_id="cid-local" if kind != "live" else "cid-live",
        broker_order_id="" if kind != "live" else "130",
        broker_order=kind == "live",
    )


def test_paper_like_kinds():
    assert is_paper_like_kind("window_paper") is True
    assert is_paper_like_kind("simulated") is True
    assert is_paper_like_kind("paper") is True
    assert is_paper_like_kind("live") is False
    assert is_paper_like_kind("reconcile_import") is False


@pytest.mark.parametrize("kind", ["paper", "simulated", "window_paper"])
def test_paper_kinds_cannot_assert_broker_open(monkeypatch, kind):
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    with pytest.raises(RuntimeError, match="local-only"):
        assert_broker_order_allowed(execution_kind=kind, action="open")


def test_paper_mode_cannot_assert_broker_even_with_live_kind(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    with pytest.raises(RuntimeError, match="EXECUTION_MODE=paper"):
        assert_broker_order_allowed(execution_kind="live", action="open")


def test_live_kind_can_assert_broker_when_live_broker(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("USE_OANDA_LIVE", "true")
    assert_broker_order_allowed(execution_kind="live", action="open")


@pytest.mark.parametrize("kind", ["window_paper", "simulated", "paper"])
def test_async_open_refuses_paper_kinds_before_api(monkeypatch, kind):
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("OANDA_ACCESS_TOKEN", "tok")
    called = {"n": 0}

    def boom(*_a, **_k):
        called["n"] += 1
        raise AssertionError("must not place a market order")

    monkeypatch.setattr("forex_bot.oanda_exec._place_market_order_open_sync", boom)

    async def _run():
        await execute_oanda_market_open(
            "EUR_USD", 2.0, "SELL", "cid-x", execution_kind=kind
        )

    with pytest.raises(RuntimeError, match="local-only"):
        asyncio.run(_run())
    assert called["n"] == 0


def test_paper_mode_open_never_calls_sync_place(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    monkeypatch.setenv("OANDA_ACCESS_TOKEN", "tok")
    called = {"n": 0}

    def boom(*_a, **_k):
        called["n"] += 1
        raise AssertionError("paper must not place")

    monkeypatch.setattr("forex_bot.oanda_exec._place_market_order_open_sync", boom)

    async def _run():
        await execute_oanda_market_open(
            "EUR_USD", 2.0, "SELL", "cid-x", execution_kind="live"
        )

    with pytest.raises(RuntimeError, match="paper"):
        asyncio.run(_run())
    assert called["n"] == 0


def test_live_open_reaches_sync_place_and_keeps_ids(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("OANDA_ACCESS_TOKEN", "tok")

    def fake_place(*_a, **_k):
        return (1.15398, 2.0, "tx-99", float("nan"))

    monkeypatch.setattr("forex_bot.oanda_exec._place_market_order_open_sync", fake_place)

    async def _run():
        return await execute_oanda_market_open(
            "EUR_USD", 2.0, "SELL", "cid-live-1", execution_kind="live"
        )

    fp, uf, oid, _pl, _ts = asyncio.run(_run())
    assert fp == pytest.approx(1.15398)
    assert uf == 2.0
    assert oid == "tx-99"
    pos = _pos("EUR_USD", kind="live")
    pos.client_order_id = "cid-live-1"
    pos.broker_order_id = oid
    pos.broker_order = True
    assert pos.broker_order is True
    assert pos.client_order_id == "cid-live-1"
    assert pos.broker_order_id == "tx-99"


def test_window_paper_fill_path_is_not_broker(monkeypatch):
    from datetime import datetime, timezone

    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("LIVE_TIMEZONE", "Europe/London")
    monkeypatch.setenv("LIVE_EUR_USD_START", "13:00")
    monkeypatch.setenv("LIVE_EUR_USD_END", "17:00")
    outside = datetime(2026, 9, 14, 18, 0, tzinfo=timezone.utc)
    assert open_fill_path("EUR_USD", at_utc=outside) == "simulate"


def test_paper_fill_path_is_not_broker(monkeypatch):
    from datetime import datetime, timezone

    monkeypatch.setenv("EXECUTION_MODE", "paper")
    inside = datetime(2026, 9, 14, 14, 0, tzinfo=timezone.utc)
    assert open_fill_path("EUR_USD", at_utc=inside) != "broker"


def test_reconcile_cannot_convert_paper_metadata_to_live():
    positions.clear()
    paper = _pos("EUR_USD", kind="window_paper")
    open_position(paper)
    assert _is_broker_backed_local(paper) is False
    import_position_from_broker("EUR_USD", -2.0, 1.15398, 1.15468, 1.15259)
    kept = positions["EUR_USD"]
    assert kept.execution_kind == "window_paper"
    assert kept.broker_order is False
    assert kept.entry_price == pytest.approx(1.15398)
    positions.clear()


def test_duplicate_client_order_id_does_not_reserve_twice(monkeypatch):
    monkeypatch.setenv("PERSIST_EXEC_ORDERS", "false")
    orders_by_client_id.clear()
    ok1 = try_begin_order_submission(
        client_order_id="cid-dup", symbol="EUR_USD", direction="SELL", units=2.0
    )
    ok2 = try_begin_order_submission(
        client_order_id="cid-dup", symbol="EUR_USD", direction="SELL", units=2.0
    )
    assert ok1 is True
    assert ok2 is False
    orders_by_client_id.clear()


def test_window_paper_position_is_not_broker_backed():
    assert _is_broker_backed_local(_pos("EUR_USD", kind="window_paper")) is False
    assert _is_broker_backed_local(_pos("EUR_USD", kind="simulated")) is False
    assert _is_broker_backed_local(_pos("EUR_USD", kind="live")) is True
    assert is_paper_like(_pos("EUR_USD", kind="window_paper")) is True
    assert is_broker_backed(_pos("EUR_USD", kind="reconcile_import")) is True
    imported = _pos("EUR_USD", kind="reconcile_import")
    imported.broker_order = True
    assert is_paper_like(imported) is False

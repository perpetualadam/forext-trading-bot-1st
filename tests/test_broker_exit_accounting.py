"""Broker-authoritative exit accounting: resolve OANDA close tx, book once, fail closed."""

from __future__ import annotations

import pytest

from forex_bot.analytics import analytics
from forex_bot.broker_exit import (
    REASON_MANUAL,
    REASON_OTHER,
    REASON_POSITION_CLOSE,
    REASON_STOP_LOSS,
    REASON_TAKE_PROFIT,
    broker_exit_open_blocked_reason,
    map_oanda_close_reason,
    pending_broker_exits,
    reset_broker_exit_state,
    resolve_broker_exit,
)
from forex_bot.positions import Position, open_position, positions
from forex_bot import reconciliation as rec


INCIDENTS = [
    {
        "trade_id": "2125",
        "tx_id": "2140",
        "symbol": "GBP_USD",
        "entry": 1.33863,
        "exit": 1.33794,
        "pl": -0.0005,
        "units": 1.0,
        "sl": 1.33801,
        "tp": 1.33987,
        "strategy": "swing_breakout",
    },
    {
        "trade_id": "2133",
        "tx_id": "2146",
        "symbol": "USD_CHF",
        "entry": 0.82328,
        "exit": 0.82274,
        "pl": -0.0010,
        "units": 2.0,
        "sl": 0.82281,
        "tp": 0.82423,
        "strategy": "swing_mean_reversion",
    },
    {
        "trade_id": "2137",
        "tx_id": "2152",
        "symbol": "USD_JPY",
        "entry": 157.28100,
        "exit": 157.213,
        "pl": -0.0007,
        "units": 2.0,
        "sl": 157.20140,
        "tp": 157.44020,
        "strategy": "scalp",
    },
    {
        "trade_id": "2161",
        "tx_id": "2164",
        "symbol": "USD_CAD",
        "entry": 1.40233,
        "exit": 1.40178,
        "pl": -0.0006,
        "units": 2.0,
        "sl": 1.40190,
        "tp": 1.40319,
        "strategy": "swing_breakout",
    },
]


def _live_pos(inc: dict, *, direction: str = "BUY") -> Position:
    return Position(
        symbol=inc["symbol"],
        direction=direction,
        units=float(inc["units"]),
        entry_price=float(inc["entry"]),
        stop_loss=float(inc["sl"]),
        take_profit=float(inc["tp"]),
        open_time=1_000_000.0,
        strategy_name=inc["strategy"],
        rl_state="s",
        execution_kind="live",
        broker_order=True,
        broker_order_id=inc["trade_id"],
        broker_trade_ids=inc["trade_id"],
    )


def _closed_trade(inc: dict, *, reason: str = "STOP_LOSS_ORDER", state: str = "CLOSED", current="0"):
    return {
        "id": inc["trade_id"],
        "instrument": inc["symbol"],
        "state": state,
        "currentUnits": current,
        "initialUnits": str(int(inc["units"]) if direction_positive(inc) else -int(inc["units"])),
        "price": str(inc["entry"]),
        "averageClosePrice": str(inc["exit"]),
        "realizedPL": f"{inc['pl']:.4f}",
        "closeTime": "2026-09-21T09:49:38.776382562Z",
        "closingTransactionIDs": [inc["tx_id"]],
    }


def direction_positive(_inc: dict) -> bool:
    return True


def _fill_tx(inc: dict, *, reason: str = "STOP_LOSS_ORDER", extra=None):
    tx = {
        "id": inc["tx_id"],
        "type": "ORDER_FILL",
        "time": "2026-09-21T09:49:38.776382562Z",
        "instrument": inc["symbol"],
        "units": str(-int(inc["units"])),
        "price": str(inc["exit"]),
        "pl": f"{inc['pl']:.4f}",
        "reason": reason,
        "tradesClosed": [
            {
                "tradeID": inc["trade_id"],
                "units": str(-int(inc["units"])),
                "realizedPL": f"{inc['pl']:.4f}",
                "price": str(inc["exit"]),
            }
        ],
    }
    if extra:
        tx.update(extra)
    return tx


@pytest.fixture(autouse=True)
def _no_live_db(monkeypatch):
    monkeypatch.setattr("forex_bot.database.insert_broker_exit_ledger", lambda *_a, **_k: True)
    monkeypatch.setattr("forex_bot.database.upsert_broker_exit_pending", lambda *_a, **_k: None)
    monkeypatch.setattr("forex_bot.database.delete_broker_exit_pending", lambda *_a, **_k: None)
    monkeypatch.setattr("forex_bot.database.broker_exit_ledger_exists", lambda *_a, **_k: False)
    monkeypatch.setattr("forex_bot.database.fetch_broker_exit_ledger", lambda: [])
    monkeypatch.setattr("forex_bot.database.fetch_broker_exit_pending", lambda: [])
    monkeypatch.setenv("PERSIST_RECONCILE_STATE", "false")
    _reset()
    yield
    _reset()


def _reset():
    positions.clear()
    reset_broker_exit_state()
    analytics.trades.clear()
    rec._have_broker_snapshot = False
    rec._last_broker_nets = {}
    rec._logged_conflict.clear()
    rec._logged_match.clear()
    rec._logged_paper_preserved.clear()
    rec._last_trade_ids = {}


def _patch_flat(monkeypatch, *, trades, transactions, order_calls=None):
    order_calls = order_calls if order_calls is not None else []

    def fake_detail():
        rec._last_trade_ids = {}
        return {}

    monkeypatch.setattr(rec, "fetch_broker_positions_detail", fake_detail)
    monkeypatch.setattr("forex_bot.oanda_exec.fetch_pending_orders_sync", lambda: [])
    monkeypatch.setattr(
        "forex_bot.oanda_exec.fetch_trade_details_sync",
        lambda tid, **_k: trades.get(str(tid)),
    )
    monkeypatch.setattr(
        "forex_bot.oanda_exec.fetch_transaction_details_sync",
        lambda xid, **_k: transactions.get(str(xid)),
    )
    monkeypatch.setattr(
        "forex_bot.oanda_exec.execute_oanda_market_close",
        lambda *_a, **_k: order_calls.append("close") or (_ for _ in ()).throw(AssertionError("no close")),
    )
    monkeypatch.setattr(
        "forex_bot.oanda_exec._place_market_order_sync",
        lambda *_a, **_k: order_calls.append("place_close")
        or (_ for _ in ()).throw(AssertionError("no place close")),
    )
    return order_calls


def test_map_oanda_reasons():
    assert map_oanda_close_reason("STOP_LOSS_ORDER") == REASON_STOP_LOSS
    assert map_oanda_close_reason("TAKE_PROFIT_ORDER") == REASON_TAKE_PROFIT
    assert map_oanda_close_reason("MARKET_ORDER_TRADE_CLOSE") == REASON_MANUAL
    assert map_oanda_close_reason("MARKET_ORDER_POSITION_CLOSEOUT") == REASON_POSITION_CLOSE
    assert map_oanda_close_reason("SOMETHING_NEW") == REASON_OTHER
    assert map_oanda_close_reason("") == REASON_OTHER


def test_resolve_does_not_infer_reason_from_price(monkeypatch):
    inc = INCIDENTS[0]
    trade = _closed_trade(inc)
    tx = _fill_tx(inc, reason="TAKE_PROFIT_ORDER")
    monkeypatch.setattr("forex_bot.oanda_exec.fetch_trade_details_sync", lambda *_a, **_k: trade)
    monkeypatch.setattr("forex_bot.oanda_exec.fetch_transaction_details_sync", lambda *_a, **_k: tx)
    lu = resolve_broker_exit("2125")
    assert lu.ok is True
    assert lu.exit is not None
    assert lu.exit.reason == REASON_TAKE_PROFIT
    assert lu.exit.oanda_reason == "TAKE_PROFIT_ORDER"
    assert lu.exit.price == 1.33794


def _run_incident(monkeypatch, inc, *, reason="STOP_LOSS_ORDER"):
    _reset()
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("RECONCILE_ACTION", "auto_fix")
    monkeypatch.setenv("PERSIST_RECONCILE_STATE", "false")
    booked: list[dict] = []
    equity_calls: list[float] = []
    monkeypatch.setattr(
        "forex_bot.trading.log_trade_pg",
        lambda *a, **k: booked.append({"args": a, "kwargs": k}),
    )
    monkeypatch.setattr("forex_bot.trading.update_equity", lambda pnl: equity_calls.append(pnl))
    open_position(_live_pos(inc))
    calls = _patch_flat(
        monkeypatch,
        trades={inc["trade_id"]: _closed_trade(inc)},
        transactions={inc["tx_id"]: _fill_tx(inc, reason=reason)},
    )
    rec.reconcile_positions_log_only()
    return booked, equity_calls, calls


def test_four_stop_loss_incidents_book_once(monkeypatch):
    for inc in INCIDENTS:
        booked, equity_calls, calls = _run_incident(monkeypatch, inc)
        assert calls == []
        assert inc["symbol"] not in positions
        assert broker_exit_open_blocked_reason(inc["symbol"]) is None
        assert pending_broker_exits() == {}
        assert len(booked) == 1
        args = booked[0]["args"]
        assert args[0] == inc["symbol"]
        assert args[3] == inc["pl"]
        assert args[5] == inc["entry"]
        assert args[6] == inc["exit"]
        diag = booked[0]["kwargs"]["diagnostics"]
        assert diag["exit_reason"] == REASON_STOP_LOSS
        assert diag["oanda_reason"] == "STOP_LOSS_ORDER"
        assert diag["closing_transaction_id"] == inc["tx_id"]
        assert diag["broker_trade_id"] == inc["trade_id"]
        assert diag["broker_exit_source"] == "OANDA_TRANSACTION"
        assert analytics.trades[-1] == inc["pl"]
        assert equity_calls == []

        rec.reconcile_positions_log_only()
        assert len(booked) == 1
        assert analytics.trades.count(inc["pl"]) == 1


def test_take_profit_manual_other_and_position_close(monkeypatch):
    cases = [
        ("TAKE_PROFIT_ORDER", REASON_TAKE_PROFIT),
        ("MARKET_ORDER_TRADE_CLOSE", REASON_MANUAL),
        ("MARKET_ORDER_POSITION_CLOSEOUT", REASON_POSITION_CLOSE),
        ("UNKNOWN_REASON", REASON_OTHER),
    ]
    for oanda_reason, mapped in cases:
        booked, _, calls = _run_incident(monkeypatch, INCIDENTS[0], reason=oanda_reason)
        assert calls == []
        assert booked[0]["kwargs"]["diagnostics"]["exit_reason"] == mapped
        assert booked[0]["kwargs"]["diagnostics"]["oanda_reason"] == oanda_reason


def test_lookup_failure_does_not_book_and_blocks_reopen(monkeypatch):
    _reset()
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("RECONCILE_ACTION", "auto_fix")
    monkeypatch.setenv("PERSIST_RECONCILE_STATE", "false")
    booked: list = []
    monkeypatch.setattr("forex_bot.trading.log_trade_pg", lambda *a, **k: booked.append(1))
    inc = INCIDENTS[0]
    open_position(_live_pos(inc))
    _patch_flat(monkeypatch, trades={}, transactions={})
    rec.reconcile_positions_log_only()
    assert booked == []
    assert analytics.trades == []
    assert inc["symbol"] not in positions
    why = broker_exit_open_blocked_reason(inc["symbol"])
    assert why is not None
    assert "pending" in why
    rec.reconcile_positions_log_only()
    assert booked == []
    assert inc["symbol"] not in positions
    assert broker_exit_open_blocked_reason(inc["symbol"]) is not None


def test_delayed_visibility_then_books(monkeypatch):
    _reset()
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("RECONCILE_ACTION", "auto_fix")
    monkeypatch.setenv("PERSIST_RECONCILE_STATE", "false")
    booked: list = []
    monkeypatch.setattr("forex_bot.trading.log_trade_pg", lambda *a, **k: booked.append(a))
    inc = INCIDENTS[1]
    open_position(_live_pos(inc))
    box = {"trade": None, "tx": None}

    def trade_fn(tid, **_k):
        return box["trade"]

    def tx_fn(xid, **_k):
        return box["tx"]

    monkeypatch.setattr(rec, "fetch_broker_positions_detail", lambda: {})
    monkeypatch.setattr("forex_bot.oanda_exec.fetch_pending_orders_sync", lambda: [])
    monkeypatch.setattr("forex_bot.oanda_exec.fetch_trade_details_sync", trade_fn)
    monkeypatch.setattr("forex_bot.oanda_exec.fetch_transaction_details_sync", tx_fn)
    rec.reconcile_positions_log_only()
    assert booked == []
    assert broker_exit_open_blocked_reason(inc["symbol"])
    box["trade"] = _closed_trade(inc)
    box["tx"] = _fill_tx(inc)
    rec.reconcile_positions_log_only()
    assert len(booked) == 1
    assert booked[0][3] == inc["pl"]
    assert broker_exit_open_blocked_reason(inc["symbol"]) is None


def test_malformed_transaction_fails_safe(monkeypatch):
    _reset()
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("RECONCILE_ACTION", "auto_fix")
    monkeypatch.setenv("PERSIST_RECONCILE_STATE", "false")
    booked: list = []
    monkeypatch.setattr("forex_bot.trading.log_trade_pg", lambda *a, **k: booked.append(1))
    inc = INCIDENTS[2]
    open_position(_live_pos(inc))
    _patch_flat(
        monkeypatch,
        trades={inc["trade_id"]: _closed_trade(inc)},
        transactions={inc["tx_id"]: {"id": inc["tx_id"]}},
    )
    rec.reconcile_positions_log_only()
    assert booked == []
    assert pending_broker_exits()[inc["symbol"]].last_error in {
        "transaction_trade_mismatch",
        "missing_exit_price",
        "missing_realized_pl",
        "missing_closed_units",
        "missing_oanda_reason",
    }


def test_partial_open_trade_not_booked(monkeypatch):
    _reset()
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("RECONCILE_ACTION", "auto_fix")
    monkeypatch.setenv("PERSIST_RECONCILE_STATE", "false")
    booked: list = []
    monkeypatch.setattr("forex_bot.trading.log_trade_pg", lambda *a, **k: booked.append(1))
    inc = INCIDENTS[3]
    open_position(_live_pos(inc))
    trade = _closed_trade(inc, state="OPEN", current="1")
    _patch_flat(
        monkeypatch,
        trades={inc["trade_id"]: trade},
        transactions={inc["tx_id"]: _fill_tx(inc)},
    )
    rec.reconcile_positions_log_only()
    assert booked == []
    assert pending_broker_exits()[inc["symbol"]].last_error == "trade_not_fully_closed"


def test_sell_zero_pl_and_missing_pl(monkeypatch):
    _reset()
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("RECONCILE_ACTION", "auto_fix")
    monkeypatch.setenv("PERSIST_RECONCILE_STATE", "false")
    booked: list = []
    monkeypatch.setattr("forex_bot.trading.log_trade_pg", lambda *a, **k: booked.append({"args": a, "kwargs": k}))
    sell = {
        "trade_id": "9001",
        "tx_id": "9002",
        "symbol": "EUR_USD",
        "entry": 1.10000,
        "exit": 1.10000,
        "pl": 0.0,
        "units": 2.0,
        "sl": 1.10100,
        "tp": 1.09800,
        "strategy": "trend",
    }
    open_position(_live_pos(sell, direction="SELL"))
    _patch_flat(
        monkeypatch,
        trades={sell["trade_id"]: _closed_trade(sell)},
        transactions={sell["tx_id"]: _fill_tx(sell, reason="STOP_LOSS_ORDER")},
    )
    rec.reconcile_positions_log_only()
    assert len(booked) == 1
    assert booked[0]["args"][2] == "SELL"
    assert booked[0]["args"][3] == 0.0
    assert analytics.trades[-1] == 0.0

    _reset()
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("RECONCILE_ACTION", "auto_fix")
    monkeypatch.setenv("PERSIST_RECONCILE_STATE", "false")
    booked.clear()
    monkeypatch.setattr("forex_bot.trading.log_trade_pg", lambda *a, **k: booked.append(1))
    missing = dict(INCIDENTS[0])
    trade = _closed_trade(missing)
    trade.pop("realizedPL")
    tx = _fill_tx(missing)
    tx.pop("pl")
    tx["tradesClosed"][0].pop("realizedPL")
    open_position(_live_pos(missing))
    _patch_flat(monkeypatch, trades={missing["trade_id"]: trade}, transactions={missing["tx_id"]: tx})
    rec.reconcile_positions_log_only()
    assert booked == []
    assert pending_broker_exits()[missing["symbol"]].last_error == "missing_realized_pl"


def test_multiple_trade_ids_require_all_closed(monkeypatch):
    _reset()
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("RECONCILE_ACTION", "auto_fix")
    monkeypatch.setenv("PERSIST_RECONCILE_STATE", "false")
    booked: list = []
    monkeypatch.setattr("forex_bot.trading.log_trade_pg", lambda *a, **k: booked.append(1))
    inc = INCIDENTS[0]
    pos = _live_pos(inc)
    pos.broker_trade_ids = "2125,2999"
    open_position(pos)
    trades = {
        "2125": _closed_trade(inc),
        "2999": {"id": "2999", "state": "OPEN", "currentUnits": "1", "instrument": "GBP_USD"},
    }
    _patch_flat(monkeypatch, trades=trades, transactions={inc["tx_id"]: _fill_tx(inc)})
    rec.reconcile_positions_log_only()
    assert booked == []
    assert "GBP_USD" not in positions
    assert pending_broker_exits()["GBP_USD"].last_error == "trade_not_fully_closed"


def test_log_only_does_not_park_or_book(monkeypatch):
    _reset()
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("RECONCILE_ACTION", "log_only")
    monkeypatch.setenv("PERSIST_RECONCILE_STATE", "false")
    booked: list = []
    monkeypatch.setattr("forex_bot.trading.log_trade_pg", lambda *a, **k: booked.append(1))
    inc = INCIDENTS[0]
    open_position(_live_pos(inc))
    _patch_flat(
        monkeypatch,
        trades={inc["trade_id"]: _closed_trade(inc)},
        transactions={inc["tx_id"]: _fill_tx(inc)},
    )
    rec.reconcile_positions_log_only()
    assert inc["symbol"] in positions
    assert booked == []
    assert pending_broker_exits() == {}


def test_idempotency_mark_exit_booked_memory(monkeypatch):
    from forex_bot.broker_exit import is_exit_booked, mark_exit_booked

    _reset()
    monkeypatch.setattr("forex_bot.database.insert_broker_exit_ledger", lambda *_a, **_k: True)
    monkeypatch.setattr("forex_bot.database.broker_exit_ledger_exists", lambda *_a, **_k: False)
    assert mark_exit_booked("2140", "2125", "GBP_USD") is True
    assert mark_exit_booked("2140", "2125", "GBP_USD") is False
    assert is_exit_booked("2140", "2125") is True


def test_restart_ledger_prevents_duplicate_book(monkeypatch):
    from forex_bot.broker_exit import account_disappeared_broker_position

    _reset()
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("RECONCILE_ACTION", "auto_fix")
    booked: list = []
    monkeypatch.setattr("forex_bot.trading.log_trade_pg", lambda *a, **k: booked.append(1))
    inc = INCIDENTS[0]
    open_position(_live_pos(inc))
    _patch_flat(
        monkeypatch,
        trades={inc["trade_id"]: _closed_trade(inc)},
        transactions={inc["tx_id"]: _fill_tx(inc)},
    )
    rec.reconcile_positions_log_only()
    assert len(booked) == 1
    reset_broker_exit_state()
    monkeypatch.setattr(
        "forex_bot.database.broker_exit_ledger_exists",
        lambda xid, tid: xid == inc["tx_id"] and tid == inc["trade_id"],
    )
    open_position(_live_pos(inc))
    rec.reconcile_positions_log_only()
    assert len(booked) == 1
    assert inc["symbol"] not in positions
    assert account_disappeared_broker_position(_live_pos(inc)) == "already"

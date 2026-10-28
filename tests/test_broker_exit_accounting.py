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
    from forex_bot.broker_close_evidence import reset_close_evidence_state
    reset_close_evidence_state()
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


def test_four_stop_loss_incidents_require_durable_close_confirmation(monkeypatch):
    for inc in INCIDENTS:
        booked, equity_calls, calls = _run_incident(monkeypatch, inc)
        lookup = resolve_broker_exit(inc["trade_id"])
        assert lookup.ok and lookup.exit is not None
        assert lookup.exit.reason == REASON_STOP_LOSS
        assert lookup.exit.realized_pl == inc["pl"]
        assert lookup.exit.price == inc["exit"]
        assert lookup.exit.closing_transaction_id == inc["tx_id"]
        retained = positions[inc["symbol"]]
        rec.reconcile_positions_log_only()
        assert positions[inc["symbol"]] is retained
        assert booked == [] and equity_calls == [] and analytics.trades == []
        assert calls == []


def test_read_only_exit_reason_attribution_never_grants_delete_authority(monkeypatch):
    for reason, mapped in [("TAKE_PROFIT_ORDER", REASON_TAKE_PROFIT), ("MARKET_ORDER", REASON_MANUAL), ("MARKET_ORDER_POSITION_CLOSEOUT", REASON_POSITION_CLOSE), ("SOMETHING_NEW", REASON_OTHER)]:
        inc = INCIDENTS[0]
        booked, equity_calls, calls = _run_incident(monkeypatch, inc, reason=reason)
        result = resolve_broker_exit(inc["trade_id"])
        assert result.ok and result.exit.reason == mapped
        assert inc["symbol"] in positions
        assert booked == [] and equity_calls == [] and calls == []
        assert analytics.trades == []


def test_lookup_failure_retains_unconfirmed_exposure_and_never_books(monkeypatch):
    from forex_bot.broker_close_evidence import broker_flat_note
    inc = INCIDENTS[0]
    booked, _, calls = _run_incident(monkeypatch, inc)
    retained = positions[inc["symbol"]]
    _patch_flat(monkeypatch, trades={}, transactions={})
    assert resolve_broker_exit(inc["trade_id"]).error == "trade_details_unavailable"
    rec.reconcile_positions_log_only()
    assert positions[inc["symbol"]] is retained
    assert broker_flat_note(inc["symbol"])
    assert retained.units > 0
    assert booked == [] and calls == [] and analytics.trades == []


def test_delayed_transaction_visibility_is_not_durable_confirmation(monkeypatch):
    inc = INCIDENTS[1]
    booked, _, calls = _run_incident(monkeypatch, inc)
    _patch_flat(monkeypatch, trades={}, transactions={})
    assert resolve_broker_exit(inc["trade_id"]).ok is False
    rec.reconcile_positions_log_only()
    _patch_flat(monkeypatch, trades={inc["trade_id"]: _closed_trade(inc)}, transactions={inc["tx_id"]: _fill_tx(inc)})
    assert resolve_broker_exit(inc["trade_id"]).ok is True
    rec.reconcile_positions_log_only()
    assert inc["symbol"] in positions
    assert booked == [] and calls == [] and analytics.trades == []


def test_malformed_transaction_fails_safe(monkeypatch):
    inc = INCIDENTS[2]
    booked, _, calls = _run_incident(monkeypatch, inc)
    _patch_flat(monkeypatch, trades={inc["trade_id"]: _closed_trade(inc)}, transactions={inc["tx_id"]: {"id": inc["tx_id"]}})
    lookup = resolve_broker_exit(inc["trade_id"])
    assert not lookup.ok
    assert lookup.error in {"transaction_trade_mismatch", "missing_exit_price", "missing_realized_pl", "missing_closed_units", "missing_oanda_reason"}
    rec.reconcile_positions_log_only()
    assert inc["symbol"] in positions
    assert booked == [] and calls == [] and analytics.trades == []


def test_partial_open_trade_not_booked(monkeypatch):
    inc = INCIDENTS[3]
    booked, _, calls = _run_incident(monkeypatch, inc)
    _patch_flat(monkeypatch, trades={inc["trade_id"]: _closed_trade(inc, state="OPEN", current="1")}, transactions={inc["tx_id"]: _fill_tx(inc)})
    assert resolve_broker_exit(inc["trade_id"]).error == "trade_not_fully_closed"
    rec.reconcile_positions_log_only()
    assert inc["symbol"] in positions
    assert booked == [] and calls == [] and analytics.trades == []


def test_sell_zero_pl_is_valid_attribution_but_missing_pl_is_not(monkeypatch):
    inc = dict(INCIDENTS[0], symbol="EUR_USD", trade_id="9001", tx_id="9002", entry=1.1, exit=1.1, pl=0.0)
    booked, _, calls = _run_incident(monkeypatch, inc)
    assert resolve_broker_exit(inc["trade_id"]).exit.realized_pl == 0.0
    trade = _closed_trade(inc)
    trade.pop("realizedPL")
    tx = _fill_tx(inc)
    tx.pop("pl")
    tx["tradesClosed"][0].pop("realizedPL")
    _patch_flat(monkeypatch, trades={inc["trade_id"]: trade}, transactions={inc["tx_id"]: tx})
    assert resolve_broker_exit(inc["trade_id"]).error == "missing_realized_pl"
    rec.reconcile_positions_log_only()
    assert inc["symbol"] in positions
    assert booked == [] and calls == [] and analytics.trades == []


def test_multiple_trade_ids_cannot_be_collapsed_into_one_close(monkeypatch, synthetic_journal):
    import asyncio
    from forex_bot.broker_close_evidence import run_guarded_live_close
    inc = INCIDENTS[0]
    pos = _live_pos(inc)
    pos.broker_trade_ids = "2125,2999"
    open_position(pos)
    calls = _patch_flat(monkeypatch, trades={"2125": _closed_trade(inc), "2999": {"id": "2999", "state": "OPEN", "currentUnits": "1", "instrument": "GBP_USD"}}, transactions={inc["tx_id"]: _fill_tx(inc)})
    assert resolve_broker_exit("2125").ok
    assert resolve_broker_exit("2999").error == "trade_not_fully_closed"
    result = asyncio.run(run_guarded_live_close(pos, reason="synthetic-test"))
    assert result.confirmation_state == "CLOSE_RECONCILIATION_REQUIRED"
    assert result.error_classification == "multiple_trade_ids"
    assert positions[inc["symbol"]] is pos
    assert calls == [] and analytics.trades == []


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


@pytest.mark.parametrize("direction", ["BUY", "SELL"])
def test_durable_confirmation_deletes_once_and_cannot_delete_a_replacement(monkeypatch, synthetic_journal, direction):
    from decimal import Decimal
    from forex_bot.broker_close_evidence import apply_transaction_body, operation_from_confirmed_journal
    from forex_bot.close_journal import account_binding
    from forex_bot.positions import close_confirmed_live_position
    inc = INCIDENTS[0]
    pos = _live_pos(inc, direction=direction)
    open_position(pos)
    tx = dict(_fill_tx(inc), accountID="ACC")
    if direction == "SELL":
        tx["units"] = str(inc["units"])
        tx["tradesClosed"][0]["units"] = str(inc["units"])
    verified = apply_transaction_body(tx, instrument=inc["symbol"], trade_id=inc["trade_id"], direction=direction, requested_units=Decimal(str(inc["units"])), transaction_id=inc["tx_id"], account_id="ACC")
    assert verified["state"] == "CLOSE_FULLY_CONFIRMED"
    row = synthetic_journal.reserve(account_binding_value=account_binding("ACC"), position_instance_id=pos.position_instance_id, position_generation=pos.position_generation, instrument=pos.symbol, trade_id=inc["trade_id"], direction=pos.direction, original_units=str(pos.units), requested_units=str(pos.units))
    token = synthetic_journal.commit_submission_intent(row["operation_id"])
    permit = synthetic_journal.issue_submission_permit(row["operation_id"], token)
    synthetic_journal.claim_network_permit(permit)
    synthetic_journal.mark(row["operation_id"], confirmation_state=verified["state"], submission_state="SENT", error_classification="", confirmed_units=verified["confirmed_units"], remaining_units=verified["remaining_units"], transaction_ids=(inc["tx_id"],))
    operation = operation_from_confirmed_journal(pos.symbol)
    assert operation is not None
    assert close_confirmed_live_position(pos.symbol, operation) is pos
    assert synthetic_journal.get(row["operation_id"])["confirmation_state"] == "CLOSE_FINALISED"
    reset_broker_exit_state()
    from forex_bot.broker_close_evidence import reset_close_evidence_state
    reset_close_evidence_state()
    replacement = _live_pos(inc)
    open_position(replacement)
    assert replacement.position_instance_id != pos.position_instance_id
    assert close_confirmed_live_position(pos.symbol, operation) is None
    assert positions[pos.symbol] is replacement
    assert analytics.trades == []


@pytest.mark.parametrize("field,value,reason", [("accountID", "OTHER", "account_mismatch"), ("instrument", "USD_JPY", "instrument_mismatch"), ("units", "1", "direction_mismatch")])
def test_foreign_or_wrong_side_transaction_cannot_confirm_close(field, value, reason):
    from decimal import Decimal
    from forex_bot.broker_close_evidence import apply_transaction_body, CloseReadError
    inc = INCIDENTS[0]
    tx = dict(_fill_tx(inc), accountID="ACC")
    tx[field] = value
    with pytest.raises(CloseReadError, match=reason):
        apply_transaction_body(tx, instrument=inc["symbol"], trade_id=inc["trade_id"], direction="BUY", requested_units=Decimal(str(inc["units"])), transaction_id=inc["tx_id"], account_id="ACC")
    assert analytics.trades == []

"""Broker authority vs local paper: Case A–E, paper skip, exposure, no order mutation."""

from __future__ import annotations

import logging

import pandas as pd
import pytest

from forex_bot.execution import is_broker_backed, is_paper_like
from forex_bot.portfolio_exposure import usd_direction_guard_decision
from forex_bot.positions import (
    Position,
    displace_paper_position,
    import_position_from_broker,
    last_displaced_paper,
    open_position,
    positions,
)
from forex_bot.profit_protection import seed_position_mfe
from forex_bot import positions as posmod
from forex_bot import reconciliation as rec
from forex_bot.broker_exit import pending_broker_exits, reset_broker_exit_state


def _paper(symbol: str = "EUR_USD", *, entry: float = 1.15398, kind: str = "window_paper") -> Position:
    return Position(
        symbol=symbol,
        direction="SELL",
        units=2.0,
        entry_price=entry,
        stop_loss=1.15468,
        take_profit=1.15259,
        open_time=0.0,
        strategy_name="trend",
        rl_state="s",
        execution_kind=kind,
        client_order_id="cid-paper",
        broker_order_id="",
        broker_order=False,
    )


def _live(symbol: str = "EUR_USD", *, entry: float = 1.15420, units: float = 2.0) -> Position:
    return Position(
        symbol=symbol,
        direction="SELL",
        units=units,
        entry_price=entry,
        stop_loss=1.15480,
        take_profit=1.15200,
        open_time=1_000_000.0,
        strategy_name="trend",
        rl_state="s",
        execution_kind="live",
        client_order_id="cid-live",
        broker_order_id="tx-orig",
        broker_order=True,
        broker_trade_ids="555",
        sl_source="broker_pending",
        tp_source="broker_pending",
    )


def _reset(rec_mod=rec):
    positions.clear()
    posmod._displaced_paper.clear()
    rec_mod._have_broker_snapshot = False
    rec_mod._last_broker_nets = {}
    rec_mod._logged_conflict.clear()
    rec_mod._logged_match.clear()
    rec_mod._logged_paper_preserved.clear()
    rec_mod._last_trade_ids = {}
    reset_broker_exit_state()


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("RECONCILE_ACTION", "log_only")
    monkeypatch.setenv("PERSIST_RECONCILE_STATE", "false")
    monkeypatch.setenv("MAX_SAME_USD_DIRECTION_POSITIONS", "2")
    monkeypatch.setattr("forex_bot.database.insert_broker_exit_ledger", lambda *_a, **_k: True)
    monkeypatch.setattr("forex_bot.database.upsert_broker_exit_pending", lambda *_a, **_k: None)
    monkeypatch.setattr("forex_bot.database.delete_broker_exit_pending", lambda *_a, **_k: None)
    monkeypatch.setattr("forex_bot.database.broker_exit_ledger_exists", lambda *_a, **_k: False)
    monkeypatch.setattr("forex_bot.database.fetch_broker_exit_ledger", lambda: [])
    monkeypatch.setattr("forex_bot.database.fetch_broker_exit_pending", lambda: [])
    monkeypatch.setattr("forex_bot.trading.log_trade_pg", lambda *_a, **_k: None)
    _reset()
    yield
    _reset()


def _patch_broker(monkeypatch, detail: dict, pending=None, trade=None, *, order_calls=None, transactions=None):
    pending = pending if pending is not None else []
    order_calls = order_calls if order_calls is not None else []
    transactions = transactions if transactions is not None else {}

    def fake_detail():
        rec._last_trade_ids = {
            rec._norm_inst(k): ["555"] for k, (net, _avg) in detail.items() if abs(float(net)) > 1e-9
        }
        return dict(detail)

    def fake_tx(xid):
        return transactions.get(str(xid))

    monkeypatch.setattr(rec, "fetch_broker_positions_detail", fake_detail)
    monkeypatch.setattr("forex_bot.oanda_exec.fetch_pending_orders_sync", lambda: list(pending))
    monkeypatch.setattr("forex_bot.oanda_exec.fetch_trade_details_sync", lambda *_a, **_k: trade)
    monkeypatch.setattr("forex_bot.oanda_exec.fetch_transaction_details_sync", fake_tx)
    monkeypatch.setattr(
        "forex_bot.oanda_exec.execute_oanda_market_open",
        lambda *_a, **_k: order_calls.append("open") or (_ for _ in ()).throw(AssertionError("no open")),
    )
    monkeypatch.setattr(
        "forex_bot.oanda_exec.execute_oanda_market_close",
        lambda *_a, **_k: order_calls.append("close") or (_ for _ in ()).throw(AssertionError("no close")),
    )
    monkeypatch.setattr(
        "forex_bot.oanda_exec._place_market_order_open_sync",
        lambda *_a, **_k: order_calls.append("place_open") or (_ for _ in ()).throw(AssertionError("no place")),
    )
    monkeypatch.setattr(
        "forex_bot.oanda_exec._place_market_order_sync",
        lambda *_a, **_k: order_calls.append("place_close") or (_ for _ in ()).throw(AssertionError("no place close")),
    )
    return order_calls


def test_import_still_refuses_to_mutate_paper_in_place():
    open_position(_paper())
    import_position_from_broker("EUR_USD", -2.0, 1.15420, 1.15480, 1.15200)
    kept = positions["EUR_USD"]
    assert kept.execution_kind == "window_paper"
    assert kept.broker_order is False
    assert kept.entry_price == pytest.approx(1.15398)


def test_displace_then_import_uses_broker_identity():
    open_position(_paper())
    snap = displace_paper_position("EUR_USD", reason="broker_authoritative")
    assert snap is not None
    assert snap["execution_kind"] == "window_paper"
    assert snap["entry_price"] == pytest.approx(1.15398)
    import_position_from_broker(
        "EUR_USD",
        -2.0,
        1.15420,
        1.15480,
        1.15200,
        sl_source="broker_pending",
        tp_source="broker_pending",
        broker_trade_ids="555",
        broker_order_id="555",
    )
    pos = positions["EUR_USD"]
    assert pos.execution_kind == "reconcile_import"
    assert pos.broker_order is True
    assert pos.entry_price == pytest.approx(1.15420)
    assert pos.direction == "SELL"
    assert pos.units == pytest.approx(2.0)
    assert is_broker_backed(pos)
    assert not is_paper_like(pos)
    assert last_displaced_paper()[-1]["entry_price"] == pytest.approx(1.15398)


def test_case_b_conflict_displaces_paper_and_imports_broker(monkeypatch, caplog):
    open_position(_paper(entry=1.15398))
    calls = _patch_broker(
        monkeypatch,
        {"EUR_USD": (-2.0, 1.15420)},
        pending=[
            {"type": "STOP_LOSS", "instrument": "EUR_USD", "price": "1.15480"},
            {"type": "TAKE_PROFIT", "instrument": "EUR_USD", "price": "1.15200"},
        ],
    )
    caplog.set_level(logging.INFO)
    mismatches = rec.reconcile_positions_log_only()
    pos = positions["EUR_USD"]
    assert pos.execution_kind == "reconcile_import"
    assert pos.entry_price == pytest.approx(1.15420)
    assert pos.direction == "SELL"
    assert pos.units == pytest.approx(2.0)
    assert pos.stop_loss == pytest.approx(1.15480)
    assert pos.take_profit == pytest.approx(1.15200)
    assert pos.sl_source == "broker_pending"
    assert pos.tp_source == "broker_pending"
    assert pos.broker_order is True
    assert last_displaced_paper()[-1]["execution_kind"] == "window_paper"
    assert last_displaced_paper()[-1]["entry_price"] == pytest.approx(1.15398)
    assert calls == []
    assert not any(m[0] == "EUR_USD" and "paper-like" in m[2] for m in mismatches)
    assert any("RECONCILE CONFLICT" in r.message for r in caplog.records)


def test_case_a_match_keeps_live_identity(monkeypatch):
    live = _live()
    open_position(live)
    _patch_broker(monkeypatch, {"EUR_USD": (-2.0, 1.15420)})
    rec.reconcile_positions_log_only()
    pos = positions["EUR_USD"]
    assert pos.execution_kind == "live"
    assert pos.client_order_id == "cid-live"
    assert pos.broker_order_id == "tx-orig"
    assert pos.entry_price == pytest.approx(1.15420)
    assert pos is live


def test_case_c_imports_when_local_empty(monkeypatch):
    _patch_broker(monkeypatch, {"EUR_USD": (-2.0, 1.15420)})
    rec.reconcile_positions_log_only()
    pos = positions["EUR_USD"]
    assert pos.execution_kind == "reconcile_import"
    assert pos.broker_order is True
    assert pos.entry_price == pytest.approx(1.15420)
    assert pos.direction == "SELL"


def test_case_d_log_only_keeps_local_broker_backed_when_broker_flat(monkeypatch):
    open_position(_live())
    _patch_broker(monkeypatch, {})
    rec.reconcile_positions_log_only()
    assert "EUR_USD" in positions
    assert positions["EUR_USD"].execution_kind == "live"


def test_case_d_auto_fix_drops_broker_backed_when_broker_flat(monkeypatch):
    monkeypatch.setenv("RECONCILE_ACTION", "auto_fix")
    open_position(_live())
    _patch_broker(monkeypatch, {})
    rec.reconcile_positions_log_only()
    assert "EUR_USD" not in positions
    pend = pending_broker_exits()
    assert "EUR_USD" in pend
    assert pend["EUR_USD"].last_error == "trade_details_unavailable"


def test_case_e_preserves_paper_when_broker_flat(monkeypatch, caplog):
    open_position(_paper())
    _patch_broker(monkeypatch, {})
    caplog.set_level(logging.INFO)
    rec.reconcile_positions_log_only()
    kept = positions["EUR_USD"]
    assert kept.execution_kind == "window_paper"
    assert kept.broker_order is False
    assert kept.entry_price == pytest.approx(1.15398)
    assert any("LOCAL PAPER PRESERVED" in r.message for r in caplog.records)


def test_paper_open_blocked_after_broker_snapshot():
    rec._remember_broker_snapshot({"EUR_USD": (-2.0, 1.15420)})
    why = rec.paper_open_blocked_reason("EUR_USD")
    assert why is not None
    assert "broker-backed" in why


def test_paper_open_allowed_before_any_snapshot():
    assert rec.paper_open_blocked_reason("EUR_USD") is None


def test_paper_open_blocked_when_local_already_broker_backed():
    open_position(_live())
    why = rec.paper_open_blocked_reason("EUR_USD")
    assert why is not None


def test_usd_guard_counts_imported_not_displaced_paper(monkeypatch):
    open_position(_paper())
    _patch_broker(monkeypatch, {"EUR_USD": (-2.0, 1.15420)})
    rec.reconcile_positions_log_only()
    assert is_broker_backed(positions["EUR_USD"])
    d = usd_direction_guard_decision("GBP_USD", "SELL")
    assert d["same_direction_count"] == 1
    assert d["exceeds"] is False
    displaced = last_displaced_paper()
    assert displaced and displaced[-1]["execution_kind"] == "window_paper"


def test_fallback_sl_tp_not_claimed_as_broker(monkeypatch):
    _patch_broker(monkeypatch, {"EUR_USD": (-2.0, 1.15420)}, pending=[], trade=None)
    rec.reconcile_positions_log_only()
    pos = positions["EUR_USD"]
    assert pos.sl_source == "local_fallback"
    assert pos.tp_source == "local_fallback"
    assert pos.entry_price == pytest.approx(1.15420)


def test_trade_details_preferred_for_sl_tp_and_open_time(monkeypatch):
    trade = {
        "id": "555",
        "openTime": "2026-09-15T17:11:22.123456789Z",
        "price": "1.15420",
        "stopLossOrder": {"type": "STOP_LOSS", "price": "1.15490"},
        "takeProfitOrder": {"type": "TAKE_PROFIT", "price": "1.15190"},
        "clientExtensions": {"id": "cid-from-trade"},
    }
    _patch_broker(monkeypatch, {"EUR_USD": (-2.0, 1.15420)}, trade=trade)
    rec.reconcile_positions_log_only()
    pos = positions["EUR_USD"]
    assert pos.sl_source == "broker_trade"
    assert pos.tp_source == "broker_trade"
    assert pos.stop_loss == pytest.approx(1.15490)
    assert pos.take_profit == pytest.approx(1.15190)
    assert pos.client_order_id == "cid-from-trade"
    assert pos.broker_order_id == "555"
    assert pos.open_time == pytest.approx(rec._parse_oanda_open_time(trade["openTime"]))


def test_mfe_seed_uses_broker_entry_and_does_not_invent_peak():
    import_position_from_broker(
        "EUR_USD",
        -2.0,
        1.15420,
        1.15480,
        1.15200,
        sl_source="broker_pending",
        tp_source="broker_pending",
        open_time=1_700_000_000.0,
    )
    pos = positions["EUR_USD"]
    assert pos.profit_protection_seeded is True
    assert pos.max_profit_pips == pytest.approx(0.0)
    current = 1.15370  # +5 pips for SELL
    src = seed_position_mfe(pos, current, None, include_partial_entry_bar=False)
    assert src == "already"
    from forex_bot.profit_protection import apply_profit_protection

    d = apply_profit_protection(pos, current)
    assert d.max_profit_pips == pytest.approx(5.0, abs=0.05)
    assert pos.profit_protection_active is False


def test_mfe_seed_from_candles_when_open_time_known():
    opened = rec._parse_oanda_open_time("2026-09-15T17:11:22.000000000Z")
    assert opened is not None
    import_position_from_broker(
        "EUR_USD",
        -2.0,
        1.15420,
        1.15480,
        1.15200,
        open_time=opened,
    )
    pos = positions["EUR_USD"]
    assert pos.profit_protection_seeded is True
    ohlcv = pd.DataFrame(
        {
            "time": ["2026-09-15T17:12:00Z", "2026-09-15T17:16:00Z"],
            "high": [1.15440, 1.15410],
            "low": [1.15300, 1.15350],
            "close": [1.15370, 1.15380],
        }
    )
    from forex_bot.profit_protection import raise_mfe_from_post_entry_ohlcv

    src = seed_position_mfe(pos, 1.15380, ohlcv, include_partial_entry_bar=False)
    assert src == "already"
    raise_mfe_from_post_entry_ohlcv(pos, ohlcv)
    # SELL MFE uses post-entry lows vs entry 1.15420 → 1.15300 = 12 pips
    assert pos.max_profit_pips == pytest.approx(12.0, abs=0.05)


def test_restart_window_paper_cannot_hide_live_broker_position(monkeypatch):
    """Realistic restart: live fill exists at OANDA; memory is lost; paper occupies the slot."""
    calls = []
    # 1–2. Bot had opened EUR_USD LIVE; OANDA still holds it.
    live_before_restart = _live(entry=1.15420)
    open_position(live_before_restart)
    assert live_before_restart.execution_kind == "live"
    # 3. Process restart loses in-memory state.
    positions.clear()
    # 4. Local window_paper occupies the only symbol slot.
    open_position(_paper(entry=1.15398))
    assert positions["EUR_USD"].execution_kind == "window_paper"
    # 5–8. Reconciliation sees OANDA EUR_USD, conflicts, displaces paper, imports broker.
    _patch_broker(
        monkeypatch,
        {"EUR_USD": (-2.0, 1.15420)},
        pending=[
            {"type": "STOP_LOSS", "instrument": "EUR_USD", "price": "1.15480"},
            {"type": "TAKE_PROFIT", "instrument": "EUR_USD", "price": "1.15200"},
        ],
        trade={
            "id": "555",
            "openTime": "2026-09-15T17:11:22.000000000Z",
            "stopLossOrder": {"price": "1.15480"},
            "takeProfitOrder": {"price": "1.15200"},
            "clientExtensions": {"id": "cid-live"},
        },
        order_calls=calls,
    )
    rec.reconcile_positions_log_only()
    pos = positions["EUR_USD"]
    # 9–10. Broker entry/side/units; marked broker-backed / reconcile_import.
    assert pos.entry_price == pytest.approx(1.15420)
    assert pos.direction == "SELL"
    assert pos.units == pytest.approx(2.0)
    assert pos.execution_kind == "reconcile_import"
    assert pos.broker_order is True
    assert is_broker_backed(pos)
    assert pos.sl_source == "broker_trade"
    assert pos.tp_source == "broker_trade"
    assert pos.stop_loss == pytest.approx(1.15480)
    assert pos.take_profit == pytest.approx(1.15200)
    # 11. Imported broker position participates in live USD-direction guard.
    d = usd_direction_guard_decision("GBP_USD", "SELL")
    assert d["same_direction_count"] == 1
    # 12. Paper no longer in the active slot / live management.
    assert not is_paper_like(pos)
    assert last_displaced_paper()[-1]["execution_kind"] == "window_paper"
    assert last_displaced_paper()[-1]["entry_price"] == pytest.approx(1.15398)
    # 13–14. No new broker order; existing SL/TP not modified (no order APIs called).
    assert calls == []
    # 15. Restart import does not invent MFE; current closeout can raise it later.
    assert pos.profit_protection_seeded is True
    assert pos.max_profit_pips == pytest.approx(0.0)
    seed = seed_position_mfe(pos, 1.15370, None, include_partial_entry_bar=False)
    assert seed == "already"
    from forex_bot.profit_protection import apply_profit_protection

    d_pp = apply_profit_protection(pos, 1.15370)
    assert d_pp.max_profit_pips == pytest.approx(5.0, abs=0.05)
    assert rec.paper_open_blocked_reason("EUR_USD") is not None


def test_gbp_usd_same_conflict_path(monkeypatch):
    open_position(_paper("GBP_USD", entry=1.34700))
    _patch_broker(monkeypatch, {"GBP_USD": (-1.0, 1.34765)})
    rec.reconcile_positions_log_only()
    pos = positions["GBP_USD"]
    assert pos.execution_kind == "reconcile_import"
    assert pos.entry_price == pytest.approx(1.34765)
    assert pos.units == pytest.approx(1.0)


def test_parse_oanda_open_time_nanoseconds():
    ts = rec._parse_oanda_open_time("2026-09-15T17:11:22.123456789Z")
    assert ts is not None
    assert ts > 1_700_000_000

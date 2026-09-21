"""Read-only broker-exit attribution and one-shot completed-trade booking.

Never sends OANDA writes. Paper/candle closes do not use this module.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from forex_bot.alerts import alert

logger = logging.getLogger(__name__)

REASON_STOP_LOSS = "broker_stop_loss"
REASON_TAKE_PROFIT = "broker_take_profit"
REASON_MANUAL = "broker_manual_close"
REASON_POSITION_CLOSE = "broker_position_close"
REASON_OTHER = "broker_other"

_OANDA_REASON_MAP = {
    "STOP_LOSS_ORDER": REASON_STOP_LOSS,
    "GUARANTEED_STOP_LOSS_ORDER": REASON_STOP_LOSS,
    "TAKE_PROFIT_ORDER": REASON_TAKE_PROFIT,
    "MARKET_ORDER": REASON_MANUAL,
    "MARKET_ORDER_TRADE_CLOSE": REASON_MANUAL,
    "MARKET_ORDER_POSITION_CLOSEOUT": REASON_POSITION_CLOSE,
    "MARKET_ORDER_DELAYED_TRADE_CLOSE": REASON_POSITION_CLOSE,
}

# In-process idempotency and fail-safe pending (also persisted when Postgres is up).
_booked: set[tuple[str, str]] = set()  # (closing_transaction_id, broker_trade_id)
_pending: dict[str, "PendingBrokerExit"] = {}  # symbol → pending snapshot


@dataclass
class BrokerExit:
    trade_id: str
    closing_transaction_id: str
    instrument: str
    units: float
    price: float
    realized_pl: float
    time: str
    reason: str
    oanda_reason: str
    oanda_type: str = ""
    fully_closed: bool = True
    raw_trade: dict[str, Any] = field(default_factory=dict)
    raw_transaction: dict[str, Any] = field(default_factory=dict)


@dataclass
class BrokerExitLookup:
    ok: bool
    exit: BrokerExit | None = None
    error: str = ""


@dataclass
class PendingBrokerExit:
    symbol: str
    broker_trade_id: str
    snapshot: dict[str, Any]
    last_error: str
    first_seen_utc: str
    last_attempt_utc: str


def reset_broker_exit_state() -> None:
    """Test isolation only."""
    _booked.clear()
    _pending.clear()


def booked_exit_keys() -> set[tuple[str, str]]:
    return set(_booked)


def pending_broker_exits() -> dict[str, PendingBrokerExit]:
    return dict(_pending)


def broker_exit_open_blocked_reason(symbol: str) -> str | None:
    """If a vanished broker trade is awaiting attribution, do not reopen the slot."""
    from forex_bot.symbols import normalize_oanda_symbol

    sym = normalize_oanda_symbol(symbol)
    pend = _pending.get(sym)
    if pend is None:
        return None
    return (
        f"broker exit pending attribution "
        f"(broker_id={pend.broker_trade_id} last_error={pend.last_error})"
    )


def map_oanda_close_reason(raw: str | None) -> str:
    key = str(raw or "").strip().upper()
    return _OANDA_REASON_MAP.get(key, REASON_OTHER)


def local_broker_trade_ids(pos: Any) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    raw_ids = str(getattr(pos, "broker_trade_ids", "") or "")
    for part in raw_ids.split(","):
        tid = part.strip()
        if tid and tid not in seen:
            seen.add(tid)
            ids.append(tid)
    bid = str(getattr(pos, "broker_order_id", "") or "").strip()
    if bid and bid not in seen:
        ids.append(bid)
    return ids


def _parse_px(raw: Any) -> float | None:
    if raw in (None, ""):
        return None
    try:
        return float(str(raw).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _closed_units(trade: dict[str, Any], tx: dict[str, Any], trade_id: str) -> float | None:
    for closed in tx.get("tradesClosed") or []:
        if not isinstance(closed, dict):
            continue
        if str(closed.get("tradeID") or "").strip() != trade_id:
            continue
        u = _parse_px(closed.get("units"))
        if u is not None:
            return abs(u)
    for key in ("initialUnits", "currentUnits"):
        u = _parse_px(trade.get(key))
        if u is not None and abs(u) > 0:
            return abs(u)
    u = _parse_px(tx.get("units"))
    if u is not None:
        return abs(u)
    return None


def _tx_belongs_to_trade(tx: dict[str, Any], trade_id: str, instrument: str) -> bool:
    want = str(trade_id).strip()
    inst = str(instrument or "").strip().upper().replace("-", "_")
    tx_inst = str(tx.get("instrument") or "").strip().upper().replace("-", "_")
    if tx_inst and inst and tx_inst != inst:
        return False
    if str(tx.get("tradeID") or "").strip() == want:
        return True
    for closed in tx.get("tradesClosed") or []:
        if isinstance(closed, dict) and str(closed.get("tradeID") or "").strip() == want:
            return True
    return False


def _closing_transaction_ids(trade: dict[str, Any]) -> list[str]:
    out: list[str] = []
    raw = trade.get("closingTransactionIDs")
    if isinstance(raw, list):
        for item in raw:
            s = str(item or "").strip()
            if s and s not in out:
                out.append(s)
    one = str(trade.get("closingTransactionID") or "").strip()
    if one and one not in out:
        out.append(one)
    return out


def resolve_broker_exit(trade_id: str) -> BrokerExitLookup:
    """
    GET TradeDetails then the closing TransactionDetails. Never writes.

    Does not infer SL/TP from price. Missing/malformed/open trades fail closed.
    """
    tid = str(trade_id or "").strip()
    if not tid:
        return BrokerExitLookup(ok=False, error="no_broker_trade_id")
    from forex_bot.oanda_exec import fetch_trade_details_sync, fetch_transaction_details_sync
    from forex_bot.symbols import normalize_oanda_symbol

    try:
        trade = fetch_trade_details_sync(tid)
    except Exception as exc:
        return BrokerExitLookup(ok=False, error=f"trade_details_error:{type(exc).__name__}")
    if not isinstance(trade, dict) or not trade:
        return BrokerExitLookup(ok=False, error="trade_details_unavailable")

    state = str(trade.get("state") or "").strip().upper()
    current_u = _parse_px(trade.get("currentUnits"))
    if state != "CLOSED" or (current_u is not None and abs(current_u) > 1e-12):
        return BrokerExitLookup(ok=False, error="trade_not_fully_closed")

    tx_ids = _closing_transaction_ids(trade)
    if not tx_ids:
        return BrokerExitLookup(ok=False, error="missing_closing_transaction_id")
    closing_id = tx_ids[-1]

    try:
        tx = fetch_transaction_details_sync(closing_id)
    except Exception as exc:
        return BrokerExitLookup(ok=False, error=f"transaction_details_error:{type(exc).__name__}")
    if not isinstance(tx, dict) or not tx:
        return BrokerExitLookup(ok=False, error="transaction_details_unavailable")

    instrument = normalize_oanda_symbol(str(trade.get("instrument") or tx.get("instrument") or ""))
    if not _tx_belongs_to_trade(tx, tid, instrument):
        return BrokerExitLookup(ok=False, error="transaction_trade_mismatch")

    price = _parse_px(trade.get("averageClosePrice"))
    if price is None:
        price = _parse_px(tx.get("price"))
    realized = _parse_px(trade.get("realizedPL"))
    if realized is None:
        realized = _parse_px(tx.get("pl"))
        closed = next(
            (
                c
                for c in (tx.get("tradesClosed") or [])
                if isinstance(c, dict) and str(c.get("tradeID") or "").strip() == tid
            ),
            None,
        )
        if realized is None and closed is not None:
            realized = _parse_px(closed.get("realizedPL"))
    if price is None or price <= 0:
        return BrokerExitLookup(ok=False, error="missing_exit_price")
    if realized is None:
        return BrokerExitLookup(ok=False, error="missing_realized_pl")

    units = _closed_units(trade, tx, tid)
    if units is None or units <= 0:
        return BrokerExitLookup(ok=False, error="missing_closed_units")

    oanda_reason = str(tx.get("reason") or "").strip()
    if not oanda_reason:
        return BrokerExitLookup(ok=False, error="missing_oanda_reason")

    closed_at = str(trade.get("closeTime") or tx.get("time") or "").strip()
    return BrokerExitLookup(
        ok=True,
        exit=BrokerExit(
            trade_id=tid,
            closing_transaction_id=str(tx.get("id") or closing_id),
            instrument=instrument,
            units=float(units),
            price=float(price),
            realized_pl=float(realized),
            time=closed_at,
            reason=map_oanda_close_reason(oanda_reason),
            oanda_reason=oanda_reason,
            oanda_type=str(tx.get("type") or ""),
            fully_closed=True,
            raw_trade=trade,
            raw_transaction=tx,
        ),
    )


def format_broker_exit_line(
    *,
    symbol: str,
    broker_id: str,
    transaction_id: str,
    reason: str,
    oanda_reason: str,
    entry: float,
    exit_price: float,
    units: float,
    realized_pl: float,
    closed_at: str,
) -> str:
    return (
        f"[BROKER EXIT] symbol={symbol} broker_id={broker_id} "
        f"transaction_id={transaction_id} reason={reason} oanda_reason={oanda_reason} "
        f"entry={float(entry):.5f} exit={float(exit_price):.5f} units={float(units):.4f} "
        f"realized_pl={float(realized_pl):.4f} closed_at={closed_at or 'n/a'} "
        f"source=OANDA_TRANSACTION"
    )


def _position_snapshot(pos: Any) -> dict[str, Any]:
    return {
        "symbol": getattr(pos, "symbol", ""),
        "direction": getattr(pos, "direction", ""),
        "units": float(getattr(pos, "units", 0.0) or 0.0),
        "entry_price": float(getattr(pos, "entry_price", 0.0) or 0.0),
        "stop_loss": float(getattr(pos, "stop_loss", 0.0) or 0.0),
        "take_profit": float(getattr(pos, "take_profit", 0.0) or 0.0),
        "open_time": float(getattr(pos, "open_time", 0.0) or 0.0),
        "strategy_name": str(getattr(pos, "strategy_name", "") or ""),
        "rl_state": str(getattr(pos, "rl_state", "") or ""),
        "execution_kind": str(getattr(pos, "execution_kind", "") or "live"),
        "client_order_id": str(getattr(pos, "client_order_id", "") or ""),
        "broker_order_id": str(getattr(pos, "broker_order_id", "") or ""),
        "broker_trade_ids": str(getattr(pos, "broker_trade_ids", "") or ""),
        "max_profit_pips": float(getattr(pos, "max_profit_pips", 0.0) or 0.0),
        "max_adverse_pips": float(getattr(pos, "max_adverse_pips", 0.0) or 0.0),
        "profit_protection_active": bool(getattr(pos, "profit_protection_active", False)),
        "profit_protection_exit_pips": getattr(pos, "profit_protection_exit_pips", None),
        "atr_at_entry_pips": getattr(pos, "atr_at_entry_pips", None),
        "protect_activated_mfe_pips": getattr(pos, "protect_activated_mfe_pips", None),
        "protect_activated_atr_pips": getattr(pos, "protect_activated_atr_pips", None),
        "protect_activated_giveback_pips": getattr(pos, "protect_activated_giveback_pips", None),
        "protect_activated_exit_pips": getattr(pos, "protect_activated_exit_pips", None),
        "atr_fallback_used": bool(getattr(pos, "atr_fallback_used", False)),
    }


def _position_from_snapshot(snap: dict[str, Any]):
    from forex_bot.positions import Position

    return Position(
        symbol=str(snap.get("symbol") or ""),
        direction=str(snap.get("direction") or "BUY"),
        units=float(snap.get("units") or 0.0),
        entry_price=float(snap.get("entry_price") or 0.0),
        stop_loss=float(snap.get("stop_loss") or 0.0),
        take_profit=float(snap.get("take_profit") or 0.0),
        open_time=float(snap.get("open_time") or 0.0),
        strategy_name=str(snap.get("strategy_name") or "unknown"),
        rl_state=str(snap.get("rl_state") or ""),
        execution_kind=str(snap.get("execution_kind") or "live"),
        client_order_id=str(snap.get("client_order_id") or ""),
        broker_order_id=str(snap.get("broker_order_id") or ""),
        broker_order=True,
        broker_trade_ids=str(snap.get("broker_trade_ids") or ""),
        max_profit_pips=float(snap.get("max_profit_pips") or 0.0),
        max_adverse_pips=float(snap.get("max_adverse_pips") or 0.0),
        profit_protection_active=bool(snap.get("profit_protection_active")),
        profit_protection_exit_pips=snap.get("profit_protection_exit_pips"),
        atr_at_entry_pips=snap.get("atr_at_entry_pips"),
        protect_activated_mfe_pips=snap.get("protect_activated_mfe_pips"),
        protect_activated_atr_pips=snap.get("protect_activated_atr_pips"),
        protect_activated_giveback_pips=snap.get("protect_activated_giveback_pips"),
        protect_activated_exit_pips=snap.get("protect_activated_exit_pips"),
        atr_fallback_used=bool(snap.get("atr_fallback_used")),
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_closed_at(raw: str) -> datetime | None:
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        if "." in s:
            head, rest = s.split(".", 1)
            frac, tz = rest, ""
            for i, ch in enumerate(rest):
                if ch in "+-" and i > 0:
                    frac, tz = rest[:i], rest[i:]
                    break
            frac = (frac + "000000")[:6]
            s = f"{head}.{frac}{tz or '+00:00'}"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def is_exit_booked(closing_transaction_id: str, broker_trade_id: str) -> bool:
    key = (str(closing_transaction_id).strip(), str(broker_trade_id).strip())
    if key in _booked:
        return True
    try:
        from forex_bot.database import broker_exit_ledger_exists

        if broker_exit_ledger_exists(key[0], key[1]):
            _booked.add(key)
            return True
    except Exception:
        pass
    return False


def mark_exit_booked(closing_transaction_id: str, broker_trade_id: str, symbol: str) -> bool:
    """Record idempotency key. Returns True if this caller won the insert."""
    key = (str(closing_transaction_id).strip(), str(broker_trade_id).strip())
    if not key[0] or not key[1]:
        return False
    if key in _booked:
        return False
    inserted = True
    try:
        from forex_bot.database import insert_broker_exit_ledger

        inserted = insert_broker_exit_ledger(key[0], key[1], symbol)
    except Exception:
        inserted = True
    if not inserted:
        _booked.add(key)
        return False
    _booked.add(key)
    return True


def _set_pending(symbol: str, broker_trade_id: str, snapshot: dict[str, Any], error: str) -> None:
    from forex_bot.symbols import normalize_oanda_symbol

    sym = normalize_oanda_symbol(symbol)
    now = _now_iso()
    prev = _pending.get(sym)
    first = prev.first_seen_utc if prev is not None else now
    _pending[sym] = PendingBrokerExit(
        symbol=sym,
        broker_trade_id=str(broker_trade_id or ""),
        snapshot=dict(snapshot),
        last_error=error,
        first_seen_utc=first,
        last_attempt_utc=now,
    )
    try:
        from forex_bot.database import upsert_broker_exit_pending

        upsert_broker_exit_pending(
            symbol=sym,
            broker_trade_id=str(broker_trade_id or ""),
            first_seen_utc=first,
            last_attempt_utc=now,
            last_error=error,
            snapshot=snapshot,
        )
    except Exception:
        pass
    logger.warning(
        "[RECONCILE BROKER EXIT PENDING] symbol=%s broker_id=%s reason=%s",
        sym,
        broker_trade_id,
        error,
    )


def clear_pending_broker_exit(symbol: str) -> None:
    from forex_bot.symbols import normalize_oanda_symbol

    sym = normalize_oanda_symbol(symbol)
    _pending.pop(sym, None)
    try:
        from forex_bot.database import delete_broker_exit_pending

        delete_broker_exit_pending(sym)
    except Exception:
        pass


def load_broker_exit_state_from_db() -> None:
    """Restore pending + booked keys after process start. Never writes OANDA."""
    try:
        from forex_bot.database import fetch_broker_exit_ledger, fetch_broker_exit_pending
    except Exception:
        return
    try:
        for row in fetch_broker_exit_ledger():
            _booked.add((str(row["closing_transaction_id"]), str(row["broker_trade_id"])))
    except Exception:
        pass
    try:
        for row in fetch_broker_exit_pending():
            sym = str(row.get("symbol") or "")
            if not sym:
                continue
            _pending[sym] = PendingBrokerExit(
                symbol=sym,
                broker_trade_id=str(row.get("broker_trade_id") or ""),
                snapshot=dict(row.get("snapshot") or {}),
                last_error=str(row.get("last_error") or "reloaded"),
                first_seen_utc=str(row.get("first_seen_utc") or _now_iso()),
                last_attempt_utc=str(row.get("last_attempt_utc") or _now_iso()),
            )
    except Exception:
        pass


def _book_resolved_exit(pos: Any, resolved: BrokerExit) -> bool:
    """Persist one completed trade. Does not PositionClose or apply NAV equity."""
    from forex_bot.trading import record_completed_trade

    key_ok = mark_exit_booked(resolved.closing_transaction_id, resolved.trade_id, pos.symbol)
    if not key_ok:
        return False

    diagnostics = None
    try:
        from forex_bot.trade_diagnostics import snapshot_from_position

        diagnostics = snapshot_from_position(
            pos, exit_reason=resolved.reason, exit_price=resolved.price
        )
    except Exception:
        logger.exception("%s: broker-exit diagnostics snapshot failed (ignored)", pos.symbol)
        diagnostics = {}
    if diagnostics is None:
        diagnostics = {}
    diagnostics.update(
        {
            "exit_reason": resolved.reason,
            "oanda_reason": resolved.oanda_reason,
            "oanda_transaction_type": resolved.oanda_type,
            "broker_trade_id": resolved.trade_id,
            "closing_transaction_id": resolved.closing_transaction_id,
            "broker_exit_source": "OANDA_TRANSACTION",
            "entry_time": float(getattr(pos, "open_time", 0.0) or 0.0),
            "closed_at": resolved.time,
            "realized_pl_account_ccy": resolved.realized_pl,
        }
    )
    record_completed_trade(
        pos.symbol,
        pos.strategy_name,
        pos.direction,
        float(resolved.units),
        float(pos.entry_price),
        realized_pnl=float(resolved.realized_pl),
        exit_price=float(resolved.price),
        execution_kind=str(getattr(pos, "execution_kind", "") or "live"),
        diagnostics=diagnostics,
        apply_equity=False,
        closed_at=_parse_closed_at(resolved.time),
    )
    line = format_broker_exit_line(
        symbol=pos.symbol,
        broker_id=resolved.trade_id,
        transaction_id=resolved.closing_transaction_id,
        reason=resolved.reason,
        oanda_reason=resolved.oanda_reason,
        entry=float(pos.entry_price),
        exit_price=resolved.price,
        units=resolved.units,
        realized_pl=resolved.realized_pl,
        closed_at=resolved.time,
    )
    logger.warning("%s", line)
    alert(line)
    logger.warning(
        "[RECONCILE BROKER EXIT CONFIRMED] symbol=%s broker_id=%s transaction_id=%s",
        pos.symbol,
        resolved.trade_id,
        resolved.closing_transaction_id,
    )
    return True


def account_disappeared_broker_position(pos: Any) -> str:
    """
    Resolve and book a vanished broker-backed local. Returns booked / pending / already.

    Production assumes one OANDA trade per symbol (OPEN_ONLY + one local slot).
    Multiple local trade IDs are all required to be fully closed before booking.
    """
    from forex_bot.positions import positions as posmap
    from forex_bot.symbols import normalize_oanda_symbol

    snap = _position_snapshot(pos)
    sym = normalize_oanda_symbol(str(getattr(pos, "symbol", "") or ""))
    ids = local_broker_trade_ids(pos)
    if not ids:
        posmap.pop(sym, None)
        _set_pending(sym, "", snap, "no_broker_trade_id")
        return "pending"

    lookups = [resolve_broker_exit(tid) for tid in ids]
    if any((not lu.ok) or lu.exit is None for lu in lookups):
        err = next((lu.error for lu in lookups if not lu.ok), "unresolved")
        posmap.pop(sym, None)
        _set_pending(sym, ids[0], snap, err)
        return "pending"
    if any(not lu.exit.fully_closed for lu in lookups if lu.exit is not None):
        posmap.pop(sym, None)
        _set_pending(sym, ids[0], snap, "trade_not_fully_closed")
        return "pending"

    booked_any = False
    already = True
    for lu in lookups:
        resolved = lu.exit
        assert resolved is not None
        if is_exit_booked(resolved.closing_transaction_id, resolved.trade_id):
            continue
        already = False
        if _book_resolved_exit(pos, resolved):
            booked_any = True
    posmap.pop(sym, None)
    if booked_any or already:
        clear_pending_broker_exit(sym)
        return "already" if already and not booked_any else "booked"
    _set_pending(sym, ids[0], snap, "book_failed")
    return "pending"


def retry_pending_broker_exits(broker_nets: dict[str, float]) -> int:
    """Retry pending attribution while the instrument stays broker-flat. Returns bookings."""
    from forex_bot.symbols import normalize_oanda_symbol

    booked = 0
    for sym, pend in list(_pending.items()):
        nk = normalize_oanda_symbol(sym)
        bnet = broker_nets.get(nk)
        if bnet is not None and abs(float(bnet)) > 1e-9:
            # A new broker position exists — old pending exit is no longer the exposure.
            clear_pending_broker_exit(nk)
            continue
        snap = dict(pend.snapshot or {})
        if not snap:
            snap = {
                "symbol": nk,
                "direction": "BUY",
                "units": 0.0,
                "entry_price": 0.0,
                "stop_loss": 0.0,
                "take_profit": 0.0,
                "open_time": 0.0,
                "strategy_name": "unknown",
                "rl_state": "",
                "execution_kind": "live",
                "broker_order_id": pend.broker_trade_id,
                "broker_trade_ids": pend.broker_trade_id,
            }
        if not snap.get("broker_order_id"):
            snap["broker_order_id"] = pend.broker_trade_id
        if not snap.get("broker_trade_ids"):
            snap["broker_trade_ids"] = pend.broker_trade_id
        pos = _position_from_snapshot(snap)
        result = account_disappeared_broker_position(pos)
        if result == "booked":
            booked += 1
    return booked

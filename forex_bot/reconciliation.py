"""
Broker-truth reconciliation: compare and converge local positions/orders to OANDA.

Never places broker orders here — local registry mutations only.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import oandapyV20.endpoints.positions as pos_ep

from forex_bot.alerts import alert
from forex_bot.config import Config
from forex_bot.oanda_client import get_api, oanda_instrument
from forex_bot import positions as posmod
from forex_bot import orders as ordmod

logger = logging.getLogger(__name__)

_reconcile_runs_total = 0
_reconcile_fixes_total = 0
# Last successful OpenPositions nets (symbol → signed units). None until first success.
_last_broker_nets: dict[str, float] = {}
_have_broker_snapshot = False
_logged_conflict: set[str] = set()
_logged_match: set[str] = set()
_logged_paper_preserved: set[str] = set()
_last_trade_ids: dict[str, list[str]] = {}


def _max_fixes_per_cycle() -> int:
    try:
        return max(0, int((os.getenv("RECONCILE_MAX_FIXES_PER_CYCLE") or "50").strip() or "50"))
    except ValueError:
        return 50


# Last run metadata (single-process; for /system and gating)
_snapshot: dict[str, Any] = {
    "last_run_utc": None,
    "last_success": None,
    "last_error": None,
    "mismatch_count": 0,
    "critical_count": 0,
    "warning_count": 0,
    "mismatches": [],
    "severities": [],
    "broker_positions_fetched": None,
    "broker_pending_orders": None,
    "reconcile_fixes_applied": 0,
    "reconcile_runs_total": 0,
    "reconcile_fixes_total": 0,
    "reconcile_max_fixes_per_cycle": 50,
}


def get_reconciliation_snapshot() -> dict[str, Any]:
    """Copy of last reconciliation result for APIs (includes live age / staleness)."""
    out = dict(_snapshot)
    age = _age_seconds_since_last_reconcile()
    out["age_seconds_since_reconcile"] = age
    out["reconcile_stale"] = reconcile_is_stale()
    out["effective_reconcile_gate"] = reconcile_gate_enforced()
    out["reconcile_persistence_enabled"] = _persist_reconcile_state_enabled()
    out["orders_local_summary"] = ordmod.orders_summary()
    out["reconcile_action"] = _reconcile_action_raw()
    out["reconcile_runs_total"] = _reconcile_runs_total
    out["reconcile_fixes_total"] = _reconcile_fixes_total
    out["reconcile_max_fixes_per_cycle"] = _max_fixes_per_cycle()
    return out


def _truthy_env(name: str, default: str = "false") -> bool:
    raw = (os.getenv(name) or default).strip().lower()
    return raw in ("1", "true", "yes", "on")


def _reconcile_action_raw() -> str:
    raw = (os.getenv("RECONCILE_ACTION") or "log_only").strip().lower()
    return raw if raw in ("log_only", "auto_fix") else "log_only"


def _age_seconds_since_last_reconcile() -> float | None:
    s = _snapshot.get("last_run_utc")
    if not s:
        return None
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - t).total_seconds()
    except Exception:
        return None


def reconcile_gate_enforced() -> bool:
    from forex_bot.execution import ExecutionMode, get_execution_mode

    m = get_execution_mode()
    if m == ExecutionMode.PAPER:
        return False
    if _truthy_env("SKIP_RECONCILE_GATE_FOR_BROKER", "false"):
        return False
    raw_rc = os.getenv("REQUIRE_CLEAN_RECONCILE_FOR_BROKER")
    if raw_rc is None or str(raw_rc).strip() == "":
        require_clean = m in (ExecutionMode.PAPER_BROKER, ExecutionMode.LIVE_BROKER)
    else:
        require_clean = _truthy_env("REQUIRE_CLEAN_RECONCILE_FOR_BROKER", "false")
    block_mismatch = _truthy_env("BLOCK_NEW_ENTRIES_ON_RECONCILE_MISMATCH", "false")
    return block_mismatch or require_clean


def reconcile_is_stale() -> bool:
    raw = (os.getenv("RECONCILE_MAX_AGE_SEC") or "300").strip()
    try:
        max_age = int(raw or "300")
    except ValueError:
        max_age = 300
    if max_age <= 0:
        return False
    age = _age_seconds_since_last_reconcile()
    if age is None:
        return True
    return age > float(max_age)


def new_entries_allowed_by_reconcile() -> bool:
    if not reconcile_gate_enforced():
        return True
    if _snapshot.get("last_success") is not True:
        return False
    if reconcile_is_stale():
        return False
    return True


def reconcile_entry_blocked_reason() -> str | None:
    if not reconcile_gate_enforced():
        return None
    if _snapshot.get("last_run_utc") is None:
        return "reconcile_never_run"
    if _snapshot.get("last_success") is not True:
        if _snapshot.get("last_error"):
            return "reconcile_broker_fetch_failed"
        if int(_snapshot.get("critical_count") or 0) > 0:
            return "reconcile_mismatch_critical"
        if int(_snapshot.get("mismatch_count") or 0) > 0:
            return "reconcile_mismatch_warning"
        return "reconcile_unclean"
    if reconcile_is_stale():
        return "reconcile_stale"
    return None


def _persist_reconcile_state_enabled() -> bool:
    raw = (os.getenv("PERSIST_RECONCILE_STATE") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def load_reconcile_state_from_db() -> None:
    global _snapshot
    from forex_bot.broker_exit import load_broker_exit_state_from_db

    load_broker_exit_state_from_db()
    if not _persist_reconcile_state_enabled():
        return
    from forex_bot.database import fetch_reconcile_metadata

    row = fetch_reconcile_metadata()
    if row is None:
        return
    if _snapshot.get("last_run_utc") is not None:
        return
    _snapshot.update(
        {
            "last_run_utc": row.get("last_run_utc"),
            "last_success": row.get("last_success"),
            "last_error": row.get("last_error"),
            "mismatch_count": int(row.get("mismatch_count") or 0),
            "critical_count": int(row.get("critical_count") or 0),
            "warning_count": int(row.get("warning_count") or 0),
            "mismatches": [],
            "severities": [],
            "broker_positions_fetched": None,
            "broker_pending_orders": None,
            "reconcile_fixes_applied": 0,
        }
    )
    logger.info(
        "reconciliation: loaded persisted metadata (last_run_utc=%s last_success=%s)",
        row.get("last_run_utc"),
        row.get("last_success"),
    )


def _save_reconcile_state_to_db() -> None:
    if not _persist_reconcile_state_enabled():
        return
    from forex_bot.database import upsert_reconcile_metadata

    upsert_reconcile_metadata(
        last_run_utc=_snapshot.get("last_run_utc"),
        last_success=_snapshot.get("last_success"),
        last_error=_snapshot.get("last_error"),
        mismatch_count=int(_snapshot.get("mismatch_count") or 0),
        critical_count=int(_snapshot.get("critical_count") or 0),
        warning_count=int(_snapshot.get("warning_count") or 0),
    )


def fetch_broker_positions_detail() -> dict[str, tuple[float, float]]:
    """
    Net signed units and average price per instrument from OANDA OpenPositions.
    Positive net = long.

    Raises when the API client or account id is missing in broker execution modes so
    reconciliation does not treat "unavailable" as a clean empty book.
    """
    from forex_bot.execution import ExecutionMode, get_execution_mode

    api = get_api()
    aid = (Config.OANDA_ACCOUNT_ID or "").strip()
    if api is None or not aid:
        mode = get_execution_mode()
        if mode in (ExecutionMode.PAPER_BROKER, ExecutionMode.LIVE_BROKER):
            raise RuntimeError(
                "reconciliation: OANDA API/account unavailable in broker mode "
                "(refusing to treat as empty broker book)"
            )
        logger.debug("reconciliation: skip fetch (no API or OANDA_ACCOUNT_ID)")
        return {}

    from forex_bot.oanda_client import _oanda_request

    r = pos_ep.OpenPositions(accountID=aid)
    try:
        resp: dict[str, Any] = _oanda_request(api, r, context="open positions")
    except Exception as exc:
        logger.warning("reconciliation: OpenPositions failed: %s", exc)
        raise

    out: dict[str, tuple[float, float]] = {}
    _last_trade_ids.clear()
    for p in resp.get("positions") or []:
        inst = oanda_instrument(str(p.get("instrument") or ""))
        if not inst:
            continue
        long_u = p.get("long") or {}
        short_u = p.get("short") or {}
        try:
            lu = float(str(long_u.get("units") or "0").replace(",", "") or 0.0)
        except (TypeError, ValueError):
            lu = 0.0
        try:
            su = float(str(short_u.get("units") or "0").replace(",", "") or 0.0)
        except (TypeError, ValueError):
            su = 0.0
        try:
            lp = float(str(long_u.get("averagePrice") or "0").replace(",", "") or 0.0)
        except (TypeError, ValueError):
            lp = 0.0
        try:
            sp = float(str(short_u.get("averagePrice") or "0").replace(",", "") or 0.0)
        except (TypeError, ValueError):
            sp = 0.0
        net = lu + su
        if abs(net) < 1e-9:
            continue
        if abs(lu) > 1e-9 and abs(su) < 1e-9:
            ap = lp
        elif abs(su) > 1e-9 and abs(lu) < 1e-9:
            ap = sp
        else:
            denom = abs(lu) + abs(su)
            ap = (abs(lu) * lp + abs(su) * sp) / denom if denom > 1e-12 else lp
        out[inst] = (net, ap)
        tids = []
        for raw_id in list(long_u.get("tradeIDs") or []) + list(short_u.get("tradeIDs") or []):
            s = str(raw_id or "").strip()
            if s:
                tids.append(s)
        _last_trade_ids[inst] = tids
    return out


def fetch_broker_open_positions() -> dict[str, float]:
    """Net long units per instrument (compat)."""
    d = fetch_broker_positions_detail()
    return {k: v[0] for k, v in d.items()}


def known_broker_net(symbol: str) -> float | None:
    """Signed broker units from the last successful OpenPositions snapshot, or None if none yet."""
    if not _have_broker_snapshot:
        return None
    return float(_last_broker_nets.get(_norm_inst(symbol), 0.0))


def paper_open_blocked_reason(symbol: str) -> str | None:
    """If a new paper/window_paper row must not occupy the symbol slot, return why."""
    from forex_bot.execution import is_broker_backed

    local = posmod.positions.get(_norm_inst(symbol)) or posmod.positions.get(symbol)
    from forex_bot.broker_exit import broker_exit_open_blocked_reason

    pending_why = broker_exit_open_blocked_reason(symbol)
    if pending_why:
        return pending_why
    if local is not None and is_broker_backed(local):
        return (
            f"broker-backed position already exists "
            f"(kind={local.execution_kind} net="
            f"{(float(local.units) if local.direction == 'BUY' else -float(local.units)):.4f})"
        )
    bnet = known_broker_net(symbol)
    if bnet is not None and abs(float(bnet)) > 1e-9:
        return f"broker-backed position already exists (net={float(bnet):.4f})"
    return None


def _remember_broker_snapshot(broker_detail: dict[str, tuple[float, float]]) -> None:
    global _have_broker_snapshot, _last_broker_nets
    _last_broker_nets = {_norm_inst(k): float(v[0]) for k, v in broker_detail.items()}
    _have_broker_snapshot = True


def _broker_execution_mode() -> bool:
    from forex_bot.execution import ExecutionMode, get_execution_mode

    return get_execution_mode() in (ExecutionMode.PAPER_BROKER, ExecutionMode.LIVE_BROKER)


def _parse_oanda_open_time(raw: Any) -> float | None:
    """OANDA RFC3339 trade openTime → epoch seconds. None if missing/unparseable."""
    if raw in (None, ""):
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        # OANDA uses nanoseconds; datetime accepts up to microseconds.
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
        return dt.timestamp()
    except (TypeError, ValueError):
        return None


def _order_price(blob: Any) -> float | None:
    if not isinstance(blob, dict):
        return None
    raw = blob.get("price")
    try:
        return float(str(raw).replace(",", "")) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _fields_from_broker_trade(trade: dict[str, Any]) -> dict[str, Any]:
    """Extract reconstructable fields from TradeDetails. Missing keys stay None/empty."""
    sl = _order_price(trade.get("stopLossOrder"))
    tp = _order_price(trade.get("takeProfitOrder"))
    opened = _parse_oanda_open_time(trade.get("openTime"))
    ce = trade.get("clientExtensions") if isinstance(trade.get("clientExtensions"), dict) else {}
    cid = str(ce.get("id") or "").strip()
    tid = str(trade.get("id") or "").strip()
    return {
        "open_time": opened,
        "sl": sl,
        "tp": tp,
        "client_order_id": cid,
        "broker_trade_id": tid,
    }


def _pending_sl_tp(symbol: str, pending: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    """STOP_LOSS / TAKE_PROFIT prices from already-fetched pending orders. None if absent."""
    sl: float | None = None
    tp: float | None = None
    want = _norm_inst(symbol)
    for bo in pending or []:
        raw = bo.get("order") if isinstance(bo.get("order"), dict) else bo
        if not isinstance(raw, dict):
            continue
        inst = _norm_inst(str(raw.get("instrument") or bo.get("instrument") or ""))
        if inst != want:
            continue
        typ = str(raw.get("type") or bo.get("type") or "").upper()
        px_raw = raw.get("price") or bo.get("price")
        try:
            px = float(str(px_raw).replace(",", "")) if px_raw not in (None, "") else None
        except (TypeError, ValueError):
            px = None
        if px is None:
            continue
        if typ in {"STOP_LOSS", "GUARANTEED_STOP_LOSS"}:
            sl = px
        elif typ == "TAKE_PROFIT":
            tp = px
    return sl, tp


def _norm_inst(s: str) -> str:
    """OANDA uses underscores; normalize hyphens/slashes and case for comparisons."""
    from forex_bot.symbols import normalize_oanda_symbol

    return normalize_oanda_symbol(s)


def _classify(sym: str, msg: str) -> str:
    if "no local position" in msg or "broker open net" in msg:
        return "critical"
    if "unit mismatch" in msg:
        return "critical"
    return "warning"


def _may_auto_fix_local() -> bool:
    """
    Auto-fix (close/adjust/import local registry) when RECONCILE_ACTION=auto_fix.

    Default: only paper_broker / live_broker so full PAPER mode is not wiped when broker snapshot is empty.

    Set RECONCILE_AUTO_FIX_IN_PAPER=true to apply the same broker-truth fixes in EXECUTION_MODE=paper
    (ghost local positions are removed when broker is flat — use only if you accept that risk).
    """
    from forex_bot.execution import ExecutionMode, get_execution_mode

    if _reconcile_action_raw() != "auto_fix":
        return False
    m = get_execution_mode()
    if m in (ExecutionMode.PAPER_BROKER, ExecutionMode.LIVE_BROKER):
        return True
    if m == ExecutionMode.PAPER and _truthy_env("RECONCILE_AUTO_FIX_IN_PAPER", "false"):
        return True
    return False


def _import_broker_truth(
    symbol: str,
    bnet: float,
    bavg: float,
    pending: list[dict[str, Any]],
) -> None:
    """Import broker units/entry. Prefer pending SL/TP; else local fallback (not claimed as broker)."""
    from forex_bot.trading import sl_tp_distance_for_entry

    sl_pending, tp_pending = _pending_sl_tp(symbol, pending)
    tids = _last_trade_ids.get(_norm_inst(symbol)) or []
    trade_fields: dict[str, Any] = {}
    if tids:
        try:
            from forex_bot.oanda_exec import fetch_trade_details_sync

            trade = fetch_trade_details_sync(tids[0])
            if isinstance(trade, dict):
                trade_fields = _fields_from_broker_trade(trade)
        except Exception as exc:
            logger.warning("reconciliation: TradeDetails lookup failed for %s: %s", symbol, exc)

    sl_b = trade_fields.get("sl") if trade_fields.get("sl") is not None else sl_pending
    tp_b = trade_fields.get("tp") if trade_fields.get("tp") is not None else tp_pending
    if trade_fields.get("sl") is not None:
        sl_src = "broker_trade"
    elif sl_pending is not None:
        sl_src = "broker_pending"
    else:
        sl_src = "local_fallback"
    if trade_fields.get("tp") is not None:
        tp_src = "broker_trade"
    elif tp_pending is not None:
        tp_src = "broker_pending"
    else:
        tp_src = "local_fallback"
    if sl_b is None or tp_b is None:
        sl_d, tp_d = sl_tp_distance_for_entry(symbol, None)
        entry = float(bavg)
        if bnet > 0:
            sl_fb, tp_fb = entry - sl_d, entry + tp_d
        else:
            sl_fb, tp_fb = entry + sl_d, entry - tp_d
        sl = sl_b if sl_b is not None else sl_fb
        tp = tp_b if tp_b is not None else tp_fb
    else:
        sl, tp = sl_b, tp_b
    from forex_bot.broker_exit import clear_pending_broker_exit

    clear_pending_broker_exit(symbol)
    posmod.import_position_from_broker(
        symbol,
        bnet,
        bavg,
        sl,
        tp,
        broker_trade_ids=",".join(tids),
        sl_source=sl_src,
        tp_source=tp_src,
        client_order_id=str(trade_fields.get("client_order_id") or ""),
        broker_order_id=tids[0] if tids else "",
        open_time=trade_fields.get("open_time"),
    )


def _apply_position_convergence(
    broker_detail: dict[str, tuple[float, float]],
    broker_pending: list[dict[str, Any]] | None = None,
) -> int:
    """CASE A/B/C/D. Never sends broker orders. Case B/C run in broker execution modes."""
    from forex_bot.execution import is_broker_backed, is_paper_like

    pending = broker_pending or []
    fixes = 0
    cap = _max_fixes_per_cycle()
    import_ok = _truthy_env("RECONCILE_IMPORT_BROKER_POSITIONS", "false") or _broker_execution_mode()
    adjust_ok = _truthy_env("RECONCILE_ADJUST_UNITS", "false")
    broker_nets = {_norm_inst(k): v[0] for k, v in broker_detail.items()}

    def _room() -> bool:
        return cap <= 0 or fixes < cap

    # Case B: paper-like local must not hide a real broker position (broker modes).
    if _broker_execution_mode():
        for sym_raw, (bnet, bavg) in list(broker_detail.items()):
            if abs(float(bnet)) < 1e-9 or not _room():
                continue
            sym = _norm_inst(sym_raw)
            local = posmod.positions.get(sym)
            if local is None or not is_paper_like(local):
                continue
            if sym not in _logged_conflict:
                logger.warning(
                    "[RECONCILE CONFLICT] %s broker position exists while local state is %s; "
                    "displacing local paper state and importing broker truth | "
                    "local_entry=%.5f broker_entry=%.5f broker_net=%.4f",
                    sym,
                    local.execution_kind,
                    float(local.entry_price),
                    float(bavg),
                    float(bnet),
                )
                _logged_conflict.add(sym)
            posmod.displace_paper_position(sym, reason="broker_authoritative")
            _import_broker_truth(sym, float(bnet), float(bavg), pending)
            fixes += 1
            logger.info("[RECONCILE IMPORT] %s imported after paper displace (broker-backed)", sym)

    # Case E: broker flat + local paper — keep simulation; log once (broker modes).
    if _broker_execution_mode():
        for sym, pos in list(posmod.positions.items()):
            if not is_paper_like(pos):
                continue
            b = broker_nets.get(_norm_inst(sym))
            if b is not None and abs(float(b)) > 1e-9:
                continue
            if sym not in _logged_paper_preserved:
                logger.info(
                    "[RECONCILE LOCAL PAPER PRESERVED] %s kind=%s entry=%.5f "
                    "(broker has no matching position; simulation lifecycle unchanged)",
                    sym,
                    pos.execution_kind,
                    float(pos.entry_price),
                )
                _logged_paper_preserved.add(sym)

    # Case A match: broker-backed local agrees with broker units — log once.
    if _broker_execution_mode():
        for sym, pos in list(posmod.positions.items()):
            if not is_broker_backed(pos):
                continue
            b = broker_nets.get(_norm_inst(sym))
            if b is None or abs(float(b)) < 1e-9:
                continue
            local_u = float(pos.units) if pos.direction == "BUY" else -float(pos.units)
            if abs(float(b) - local_u) > max(1.0, 0.01 * abs(local_u)):
                continue
            if sym not in _logged_match:
                logger.info(
                    "[RECONCILE MATCH] %s kind=%s local_net=%.4f broker_net=%.4f entry=%.5f",
                    sym,
                    pos.execution_kind,
                    local_u,
                    float(b),
                    float(pos.entry_price),
                )
                _logged_match.add(sym)

    if _may_auto_fix_local():
        for sym, pos in list(posmod.positions.items()):
            if not _room():
                logger.warning("[RECONCILE FIX] cap reached (%s); defer remaining fixes", cap)
                break
            # Case E: paper-like + broker flat — keep the simulation row.
            if is_paper_like(pos):
                continue
            if not is_broker_backed(pos):
                continue
            b = broker_nets.get(_norm_inst(sym))
            local_u = float(pos.units) if pos.direction == "BUY" else -float(pos.units)
            if b is None or abs(float(b)) < 1e-9:
                # Case D: broker flat — attribute the OANDA close before dropping exposure.
                from forex_bot.broker_exit import account_disappeared_broker_position

                result = account_disappeared_broker_position(pos)
                fixes += 1
                if result == "pending":
                    logger.warning(
                        "[RECONCILE BROKER POSITION MISSING] %s awaiting broker exit tx | fix=%s/%s",
                        sym,
                        fixes,
                        cap or "inf",
                    )
                continue
            if (
                adjust_ok
                and _room()
                and abs(b - local_u) > max(1.0, 0.01 * max(abs(local_u), 1.0))
            ):
                posmod.adjust_position_units_to_broker(sym, b)
                fixes += 1
                logger.info("[RECONCILE UPDATE] adjusted units | %s | fix=%s/%s", sym, fixes, cap or "inf")

    if import_ok:
        for sym_raw, (bnet, bavg) in broker_detail.items():
            if not _room():
                break
            if abs(bnet) < 1e-9:
                continue
            sym = _norm_inst(sym_raw)
            if sym in posmod.positions:
                continue
            # Case C
            _import_broker_truth(sym, float(bnet), float(bavg), pending)
            fixes += 1
            logger.info("[RECONCILE IMPORT] imported broker-only | %s | fix=%s/%s", sym, fixes, cap or "inf")

    from forex_bot.broker_exit import retry_pending_broker_exits

    booked_pending = retry_pending_broker_exits(broker_nets)
    fixes += int(booked_pending)

    return fixes


def _is_broker_backed_local(pos: Any) -> bool:
    from forex_bot.execution import is_broker_backed

    return is_broker_backed(pos)


def _reconcile_pending_orders(broker_pending: list[dict[str, Any]]) -> None:
    """CASE D/E: local pending vs broker pending (no broker order placement)."""
    broker_ids = {str(o.get("id") or "") for o in broker_pending if o.get("id")}
    broker_ids.discard("")

    for _cid, lo in list(ordmod.orders_by_client_id.items()):
        if lo.status != ordmod.OrderStatus.PENDING:
            continue
        bid = (lo.broker_order_id or "").strip()
        if not bid:
            continue
        if bid not in broker_ids:
            ordmod.update_order(lo.client_order_id, status=ordmod.OrderStatus.CANCELLED, detail="absent_on_broker")
            logger.info(
                "[ORDER CANCELLED] local pending client=%s broker=%s not on broker pending list",
                lo.client_order_id,
                bid,
            )

    seen: set[str] = set()
    for bo in broker_pending:
        raw = bo.get("order") if isinstance(bo.get("order"), dict) else bo
        oid = str(raw.get("id") or bo.get("id") or "")
        if not oid or oid in seen:
            continue
        seen.add(oid)
        if ordmod.get_order_by_broker_id(oid):
            continue
        inst = str(raw.get("instrument") or bo.get("instrument") or "").strip()
        try:
            units_raw = raw.get("units") or raw.get("remainingUnits") or bo.get("units") or "0"
            u = float(str(units_raw).replace(",", ""))
        except (TypeError, ValueError):
            u = 0.0
        state = str(raw.get("state") or raw.get("status") or bo.get("state") or "").upper()
        st = ordmod.OrderStatus.PENDING
        if "CANCEL" in state:
            st = ordmod.OrderStatus.CANCELLED
        elif "PARTIAL" in state or "PARTIALLY" in state:
            st = ordmod.OrderStatus.PARTIAL
        cid = f"import-{oid}"
        lo = ordmod.LocalOrder(
            client_order_id=cid,
            symbol=inst or "?",
            direction="BUY" if u > 0 else "SELL",
            units_requested=abs(u),
            units_filled=0.0,
            status=st,
            avg_fill_price=None,
            created_ts=datetime.now(timezone.utc).timestamp(),
            broker_order_id=oid,
            source="reconcile_import",
            detail="imported from broker pending",
        )
        ordmod.register_order(lo)
        logger.info("[ORDER IMPORT] broker pending id=%s %s units=%s", oid, inst, u)


def reconcile_positions_log_only() -> list[tuple[str, str, str]]:
    """
    Full broker reconciliation: optional local convergence, order sync, mismatch report.
    Does not send broker orders.
    """
    global _snapshot, _reconcile_runs_total, _reconcile_fixes_total
    now = datetime.now(timezone.utc).isoformat()
    _reconcile_runs_total += 1
    err: str | None = None
    broker_detail: dict[str, tuple[float, float]] = {}
    broker_pending: list[dict[str, Any]] = []
    fixes = 0

    try:
        broker_detail = fetch_broker_positions_detail()
    except Exception as exc:
        err = str(exc)
        logger.warning("reconciliation: fetch failed: %s", exc)

    if err is None:
        try:
            from forex_bot import oanda_exec

            broker_pending = oanda_exec.fetch_pending_orders_sync()
        except Exception as exc:
            logger.warning("reconciliation: pending orders fetch failed: %s", exc)

    if err is None:
        _remember_broker_snapshot(broker_detail)
        fixes = _apply_position_convergence(broker_detail, broker_pending)
        _reconcile_fixes_total += fixes
        try:
            _reconcile_pending_orders(broker_pending)
        except Exception as exc:
            logger.warning("reconciliation: order reconcile failed: %s", exc)

    broker = {_norm_inst(k): v[0] for k, v in broker_detail.items()}
    mismatches: list[tuple[str, str, str]] = []

    if err is None:
        local_norm = {_norm_inst(s) for s in posmod.positions}
        for sym, pos in posmod.positions.items():
            if not _is_broker_backed_local(pos):
                continue
            nk = _norm_inst(sym)
            b = broker.get(nk)
            local_u = float(pos.units) if pos.direction == "BUY" else -float(pos.units)
            if b is None:
                msg = f"local open position but broker net=0 (local net units≈{local_u:.4f})"
                sev = _classify(sym, msg)
                mismatches.append((sym, sev, msg))
                continue
            if abs(b - local_u) > max(1.0, 0.01 * abs(local_u)):
                msg = f"unit mismatch broker_net={b:.4f} vs local_net≈{local_u:.4f}"
                mismatches.append((sym, "critical", msg))

        for nk, bnet in broker.items():
            if abs(bnet) < 1e-9:
                continue
            if nk not in local_norm:
                msg = f"broker open net={bnet:.4f} but no local position"
                mismatches.append((nk, "critical", msg))
            else:
                # Broker open but only a non-broker-backed local exists → still critical.
                local_pos = posmod.positions.get(nk) or next(
                    (p for s, p in posmod.positions.items() if _norm_inst(s) == nk),
                    None,
                )
                if local_pos is not None and not _is_broker_backed_local(local_pos):
                    msg = (
                        f"broker open net={bnet:.4f} but local is still paper-like "
                        f"(execution_kind={local_pos.execution_kind}) after conflict resolution"
                    )
                    mismatches.append((nk, "critical", msg))

    crit = sum(1 for m in mismatches if m[1] == "critical")
    warn = len(mismatches) - crit

    _snapshot = {
        "last_run_utc": now,
        "last_success": err is None and len(mismatches) == 0,
        "last_error": err,
        "mismatch_count": len(mismatches),
        "critical_count": crit,
        "warning_count": warn,
        "mismatches": [(m[0], m[2]) for m in mismatches],
        "severities": [m[1] for m in mismatches],
        "broker_positions_fetched": len(broker) if err is None else None,
        "broker_pending_orders": len(broker_pending) if err is None else None,
        "reconcile_fixes_applied": fixes,
        "reconcile_runs_total": _reconcile_runs_total,
        "reconcile_fixes_total": _reconcile_fixes_total,
        "reconcile_max_fixes_per_cycle": _max_fixes_per_cycle(),
    }

    if err:
        try:
            alert(f"RECONCILE ERROR: {err}")
        except Exception:
            pass
    elif mismatches:
        for sym, sev, msg in mismatches:
            logfn = logger.critical if sev == "critical" else logger.warning
            logfn("reconciliation [%s] | %s: %s", sev, sym, msg)
        if err is None and fixes == 0 and not _may_auto_fix_local():
            logger.warning(
                "reconciliation: %s mismatch(es) were not auto-fixed — set RECONCILE_ACTION=auto_fix "
                "and EXECUTION_MODE=paper_broker or live_broker (recommended), or set "
                "RECONCILE_AUTO_FIX_IN_PAPER=true if you use EXECUTION_MODE=paper. "
                "That drops ghost local positions when the broker is flat (no broker orders).",
                len(mismatches),
            )
        try:
            alert(
                f"RECONCILE: {len(mismatches)} mismatch(es) "
                f"(critical={crit}, warning={warn}) — {mismatches[:3]}"
            )
        except Exception:
            pass

    _save_reconcile_state_to_db()

    return mismatches


def run_reconciliation_once() -> None:
    reconcile_positions_log_only()

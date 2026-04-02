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
from forex_bot.oanda_client import get_api
from forex_bot import positions as posmod
from forex_bot import orders as ordmod

logger = logging.getLogger(__name__)

_reconcile_runs_total = 0
_reconcile_fixes_total = 0


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
    Positive net = long. Empty if API unavailable.
    """
    api = get_api()
    aid = (Config.OANDA_ACCOUNT_ID or "").strip()
    if api is None or not aid:
        logger.debug("reconciliation: skip fetch (no API or OANDA_ACCOUNT_ID)")
        return {}

    r = pos_ep.OpenPositions(accountID=aid)
    try:
        resp: dict[str, Any] = api.request(r)
    except Exception as exc:
        logger.warning("reconciliation: OpenPositions failed: %s", exc)
        raise

    out: dict[str, tuple[float, float]] = {}
    for p in resp.get("positions") or []:
        inst = str(p.get("instrument") or "").strip()
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
    return out


def fetch_broker_open_positions() -> dict[str, float]:
    """Net long units per instrument (compat)."""
    d = fetch_broker_positions_detail()
    return {k: v[0] for k, v in d.items()}


def _classify(sym: str, msg: str) -> str:
    if "no local position" in msg or "broker open net" in msg:
        return "critical"
    if "unit mismatch" in msg:
        return "critical"
    return "warning"


def _may_auto_fix_local() -> bool:
    """Never auto-fix in full paper simulation; only broker execution modes."""
    from forex_bot.execution import ExecutionMode, get_execution_mode

    if _reconcile_action_raw() != "auto_fix":
        return False
    return get_execution_mode() in (ExecutionMode.PAPER_BROKER, ExecutionMode.LIVE_BROKER)


def _apply_position_convergence(
    broker_detail: dict[str, tuple[float, float]],
) -> int:
    """CASE A/B/C. Returns count of fix actions (capped per cycle)."""
    from forex_bot.trading import sl_tp_distance_for_entry

    fixes = 0
    cap = _max_fixes_per_cycle()
    import_ok = _truthy_env("RECONCILE_IMPORT_BROKER_POSITIONS", "false")
    adjust_ok = _truthy_env("RECONCILE_ADJUST_UNITS", "false")

    broker_nets = {k: v[0] for k, v in broker_detail.items()}

    def _room() -> bool:
        return cap <= 0 or fixes < cap

    if _may_auto_fix_local():
        for sym, pos in list(posmod.positions.items()):
            if not _room():
                logger.warning("[RECONCILE FIX] cap reached (%s); defer remaining fixes", cap)
                break
            b = broker_nets.get(sym)
            local_u = float(pos.units) if pos.direction == "BUY" else -float(pos.units)
            if b is None or abs(float(b)) < 1e-9:
                posmod.close_local_position(sym, reason="reconcile_fix_broker_flat")
                fixes += 1
                logger.warning(
                    "[RECONCILE FIX] Closed local position (broker net=0) | %s | fix=%s/%s",
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
                logger.info("[RECONCILE FIX] adjusted units | %s | fix=%s/%s", sym, fixes, cap or "inf")

        if import_ok:
            for sym, (bnet, bavg) in broker_detail.items():
                if not _room():
                    break
                if sym in posmod.positions:
                    continue
                if abs(bnet) < 1e-9:
                    continue
                sl_d, tp_d = sl_tp_distance_for_entry(sym, None)
                entry = float(bavg)
                if bnet > 0:
                    sl = entry - sl_d
                    tp = entry + tp_d
                else:
                    sl = entry + sl_d
                    tp = entry - tp_d
                posmod.import_position_from_broker(
                    sym,
                    bnet,
                    bavg,
                    sl,
                    tp,
                )
                fixes += 1
                logger.info("[RECONCILE IMPORT] imported broker-only | %s | fix=%s/%s", sym, fixes, cap or "inf")

    return fixes


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
        fixes = _apply_position_convergence(broker_detail)
        _reconcile_fixes_total += fixes
        try:
            _reconcile_pending_orders(broker_pending)
        except Exception as exc:
            logger.warning("reconciliation: order reconcile failed: %s", exc)

    broker = {k: v[0] for k, v in broker_detail.items()}
    mismatches: list[tuple[str, str, str]] = []

    if err is None:
        for sym, pos in posmod.positions.items():
            b = broker.get(sym)
            local_u = float(pos.units) if pos.direction == "BUY" else -float(pos.units)
            if b is None:
                msg = f"local open position but broker net=0 (local net units≈{local_u:.4f})"
                sev = _classify(sym, msg)
                mismatches.append((sym, sev, msg))
                continue
            if abs(b - local_u) > max(1.0, 0.01 * abs(local_u)):
                msg = f"unit mismatch broker_net={b:.4f} vs local_net≈{local_u:.4f}"
                mismatches.append((sym, "critical", msg))

        for sym in broker:
            if sym not in posmod.positions:
                msg = f"broker open net={broker[sym]:.4f} but no local position"
                mismatches.append((sym, "critical", msg))

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

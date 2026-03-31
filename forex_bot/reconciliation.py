"""
Compare in-memory positions to OANDA open positions (log-only; state for operations API).

Future: optionally reconcile pending orders / partial fills against broker order state.
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

logger = logging.getLogger(__name__)

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
}


def get_reconciliation_snapshot() -> dict[str, Any]:
    """Copy of last reconciliation result for APIs (includes live age / staleness)."""
    out = dict(_snapshot)
    age = _age_seconds_since_last_reconcile()
    out["age_seconds_since_reconcile"] = age
    out["reconcile_stale"] = reconcile_is_stale()
    out["effective_reconcile_gate"] = reconcile_gate_enforced()
    out["reconcile_persistence_enabled"] = _persist_reconcile_state_enabled()
    return out


def _truthy_env(name: str, default: str = "false") -> bool:
    raw = (os.getenv(name) or default).strip().lower()
    return raw in ("1", "true", "yes", "on")


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
    """
    True when broker-mode reconcile policy is active (same conditions that can block entries).
    Exposed for /system so operators need not mentally combine env flags.
    """
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
    """
    True when last reconcile is missing or older than ``RECONCILE_MAX_AGE_SEC`` (default 300).
    Set ``RECONCILE_MAX_AGE_SEC=0`` to disable staleness checks (not recommended for broker gating).
    """
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
    """
    Optional gate for **new** entries (broker modes only).

    - If ``EXECUTION_MODE`` is ``paper``, always allowed.
    - ``SKIP_RECONCILE_GATE_FOR_BROKER=true`` disables this gate (explicit opt-out).
    - When ``REQUIRE_CLEAN_RECONCILE_FOR_BROKER`` is **unset**, it defaults **on** for
      ``paper_broker`` / ``live_broker`` (set to ``false`` explicitly to turn off).
    - ``BLOCK_NEW_ENTRIES_ON_RECONCILE_MISMATCH=true`` adds the same enforcement when
      ``REQUIRE_CLEAN_RECONCILE_FOR_BROKER`` is explicitly ``false``.
    - When enforcement applies: require ``last_success``, and reconcile must not be stale
      (see ``RECONCILE_MAX_AGE_SEC``).

    Pending / partial orders are not yet compared; see module TODO for future extension.
    """
    if not reconcile_gate_enforced():
        return True

    if _snapshot.get("last_success") is not True:
        return False
    if reconcile_is_stale():
        return False
    return True


def reconcile_entry_blocked_reason() -> str | None:
    """
    When :func:`reconcile_gate_enforced` is active and entries are blocked, a specific reason
    for dashboards and logs (None if entries are allowed by reconcile policy).
    """
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
    """Merge last persisted reconcile row into memory (startup / after DB reconnect)."""
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


def fetch_broker_open_positions() -> dict[str, float]:
    """
    Net long units per instrument from OANDA (positive = net long, negative = net short).
    Empty dict if API unavailable.
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

    out: dict[str, float] = {}
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
        net = lu + su
        if abs(net) > 1e-9:
            out[inst] = net
    return out


def _classify(sym: str, msg: str) -> str:
    """warning = local-only drift; critical = broker-only or unit mismatch."""
    if "no local position" in msg or "broker open net" in msg:
        return "critical"
    if "unit mismatch" in msg:
        return "critical"
    return "warning"


def reconcile_positions_log_only() -> list[tuple[str, str, str]]:
    """
    Compare broker vs local registry. Does **not** mutate local state.

    Returns list of (symbol, severity, message).
    """
    global _snapshot
    now = datetime.now(timezone.utc).isoformat()
    broker: dict[str, float] = {}
    err: str | None = None
    try:
        broker = fetch_broker_open_positions()
    except Exception as exc:
        err = str(exc)
        logger.warning("reconciliation: fetch failed: %s", exc)

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

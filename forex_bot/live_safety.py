"""Durable fail-closed live-order authorisation and strategy activation state.

JSON file persistence (no live database migration). Missing or corrupt state
blocks new live orders. Closes / protective exits are not gated here.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
AUTH_BLOCKED = "BLOCKED"
AUTH_ALLOWED = "ALLOWED"
REASON_DEFAULT_DENY = "default_deny_no_durable_state"
REASON_CORRUPT = "corrupt_or_unreadable_state"
REASON_PERSIST_FAIL = "persistence_failure"
REASON_EVOLVE = "evolve_negative_sharpe"
REASON_NOT_AUTHORISED = "not_authorised_for_live"
REASON_PROCESS_START = "process_start_requires_operator_authorisation"
REASON_PERSISTED_ALLOWED_IGNORED = "persisted_allowed_ignored_until_operator_action"
KNOWN_STRATEGY_NAMES = (
    "scalp",
    "trend",
    "mean_reversion",
    "swing_trend",
    "swing_mean_reversion",
    "swing_breakout",
)

_lock = threading.RLock()
_initialised = False
_state_valid = False
_effective_auth_state = AUTH_BLOCKED
_effective_auth_reason = REASON_PROCESS_START
_effective_auth_updated_at: str | None = None
_persisted_auth_state = AUTH_BLOCKED
_persisted_auth_reason = REASON_DEFAULT_DENY
_persisted_auth_updated_at: str | None = None
_loaded_from_durable = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def state_path() -> Path:
    raw = (os.getenv("LIVE_SAFETY_STATE_PATH") or "").strip()
    if raw:
        return Path(raw)
    return Path("data") / "ops" / "live_safety_state.json"


def live_order_auth_state() -> str:
    """Effective runtime authorisation used by the order gate (never unverified persisted ALLOWED)."""
    return _effective_auth_state if _effective_auth_state in (AUTH_BLOCKED, AUTH_ALLOWED) else AUTH_BLOCKED


def live_order_auth_reason() -> str:
    return _effective_auth_reason or REASON_PROCESS_START


def persisted_live_order_auth_state() -> str:
    return _persisted_auth_state if _persisted_auth_state in (AUTH_BLOCKED, AUTH_ALLOWED) else AUTH_BLOCKED


def persisted_live_order_auth_reason() -> str:
    return _persisted_auth_reason or REASON_DEFAULT_DENY


def live_safety_initialised() -> bool:
    return _initialised and _state_valid


def live_open_blocked_reason() -> str | None:
    """None if a new live OrderCreate is authorised; otherwise a stable reason code."""
    with _lock:
        if not _initialised or not _state_valid:
            return "live_order_auth_uninitialised"
        if live_order_auth_state() != AUTH_ALLOWED:
            return "live_order_auth_blocked"
        return None


def assert_new_live_exposure_allowed(*, action: str = "open") -> None:
    """Fail closed for new exposure. ``close`` is not a new-exposure action."""
    act = (action or "open").strip().lower()
    if act in ("close", "position_close", "flatten"):
        return
    reason = live_open_blocked_reason()
    if reason:
        raise RuntimeError(
            f"LIVE_ORDER_AUTH blocked action={act} reason={reason} "
            f"detail={live_order_auth_reason()}"
        )


def _empty_strategy_record(*, reason: str, active: bool = False) -> dict[str, Any]:
    return {
        "active": bool(active),
        "authorised_for_live": False,
        "disable_reason": reason,
        "changed_at_utc": _utc_now(),
        "sample_count": 0,
        "sharpe": None,
        "loaded_from_durable": False,
    }


def _blank_document(*, reason: str) -> dict[str, Any]:
    now = _utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "state_valid": True,
        "live_order_authorisation": {
            "state": AUTH_BLOCKED,
            "reason": reason,
            "updated_at_utc": now,
            "source": "fail_closed",
        },
        "strategies": {
            name: _empty_strategy_record(reason=reason) for name in KNOWN_STRATEGY_NAMES
        },
    }


def _validate_document(blob: Any) -> dict[str, Any] | None:
    if not isinstance(blob, dict):
        return None
    try:
        ver = int(blob.get("schema_version") or 0)
    except (TypeError, ValueError):
        return None
    if ver != SCHEMA_VERSION:
        return None
    auth = blob.get("live_order_authorisation")
    if not isinstance(auth, dict):
        return None
    state = str(auth.get("state") or "").strip().upper()
    if state not in (AUTH_BLOCKED, AUTH_ALLOWED):
        return None
    strategies = blob.get("strategies")
    if not isinstance(strategies, dict) or not strategies:
        return None
    for name in KNOWN_STRATEGY_NAMES:
        row = strategies.get(name)
        if not isinstance(row, dict):
            return None
        if "active" not in row:
            return None
    return blob


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(payload, indent=2, sort_keys=True)
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _read_document(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8-sig")
        blob = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    return _validate_document(blob)


def _record_persisted_auth(doc: dict[str, Any]) -> None:
    global _persisted_auth_state, _persisted_auth_reason, _persisted_auth_updated_at
    raw_auth = doc.get("live_order_authorisation")
    auth: dict[str, Any] = raw_auth if isinstance(raw_auth, dict) else {}
    state = str(auth.get("state") or AUTH_BLOCKED).strip().upper()
    _persisted_auth_state = state if state in (AUTH_BLOCKED, AUTH_ALLOWED) else AUTH_BLOCKED
    _persisted_auth_reason = str(auth.get("reason") or REASON_DEFAULT_DENY)
    _persisted_auth_updated_at = str(auth.get("updated_at_utc") or "") or None


def _set_effective_blocked(*, reason: str) -> None:
    global _effective_auth_state, _effective_auth_reason, _effective_auth_updated_at
    _effective_auth_state = AUTH_BLOCKED
    _effective_auth_reason = reason
    _effective_auth_updated_at = _utc_now()


def _apply_strategies_from_doc(doc: dict[str, Any]) -> None:
    from forex_bot.strategy_meta import strategies

    rows = doc.get("strategies") or {}
    for name, strat in strategies.items():
        row = rows.get(name) if isinstance(rows.get(name), dict) else None
        if row is None:
            strat.active = False
            strat.disable_reason = REASON_CORRUPT
            strat.changed_at_utc = _utc_now()
            strat.loaded_from_durable = False
            strat.authorised_for_live = False
            continue
        strat.active = bool(row.get("active"))
        strat.authorised_for_live = bool(row.get("authorised_for_live"))
        strat.disable_reason = row.get("disable_reason")
        strat.changed_at_utc = row.get("changed_at_utc")
        strat.loaded_from_durable = True
        if not strat.active:
            strat.authorised_for_live = False


def _snapshot_strategies_into(doc: dict[str, Any]) -> None:
    from forex_bot.strategy_meta import strategies

    out: dict[str, Any] = dict(doc.get("strategies") or {})
    for name, strat in strategies.items():
        try:
            sharpe = float(strat.sharpe())
        except Exception:
            sharpe = None
        pnl = getattr(strat, "pnl", None)
        n = len(pnl) if pnl is not None else 0
        raw_prev = out.get(name)
        prev = raw_prev if isinstance(raw_prev, dict) else {}
        out[name] = {
            "active": bool(getattr(strat, "active", False)),
            "authorised_for_live": bool(getattr(strat, "authorised_for_live", False)),
            "disable_reason": getattr(strat, "disable_reason", None) or prev.get("disable_reason"),
            "changed_at_utc": getattr(strat, "changed_at_utc", None) or prev.get("changed_at_utc"),
            "sample_count": n,
            "sharpe": sharpe,
            "loaded_from_durable": bool(getattr(strat, "loaded_from_durable", False)),
        }
    doc["strategies"] = out


def _persist_unlocked(doc: dict[str, Any]) -> None:
    """Write durable state. Never copies persisted ALLOWED into effective runtime auth."""
    global _state_valid
    path = state_path()
    try:
        _atomic_write(path, doc)
        _state_valid = True
        _record_persisted_auth(doc)
    except OSError as exc:
        logger.error("live safety persist failed: %s", exc)
        _state_valid = False
        _set_effective_blocked(reason=REASON_PERSIST_FAIL)
        raise


def initialise_fail_closed() -> dict[str, Any]:
    """Load durable strategy state. Effective live-order auth is always BLOCKED on process start."""
    global _initialised, _state_valid, _loaded_from_durable
    with _lock:
        path = state_path()
        doc = _read_document(path)
        if doc is None:
            reason = REASON_CORRUPT if path.exists() else REASON_DEFAULT_DENY
            logger.warning("live safety: %s path=%s — fail closed", reason, path)
            doc = _blank_document(reason=reason)
            _loaded_from_durable = False
            _apply_strategies_from_doc(doc)
            _set_effective_blocked(reason=reason)
        else:
            _loaded_from_durable = True
            _state_valid = True
            _record_persisted_auth(doc)
            _apply_strategies_from_doc(doc)
            if persisted_live_order_auth_state() == AUTH_ALLOWED:
                _set_effective_blocked(reason=REASON_PERSISTED_ALLOWED_IGNORED)
            else:
                _set_effective_blocked(reason=REASON_PROCESS_START)
        _snapshot_strategies_into(doc)
        try:
            _persist_unlocked(doc)
        except OSError:
            _initialised = True
            _state_valid = False
            _set_effective_blocked(reason=REASON_PERSIST_FAIL)
            return doc
        _initialised = True
        logger.info(
            "live safety initialised effective=%s persisted=%s reason=%s valid=%s path=%s",
            live_order_auth_state(),
            persisted_live_order_auth_state(),
            live_order_auth_reason(),
            _state_valid,
            path,
        )
        return doc


def persist_evolve_disable(name: str, *, sample_count: int, sharpe: float) -> None:
    """Keep evolve() disable durable. Does not reactivate any strategy."""
    with _lock:
        if not _initialised:
            initialise_fail_closed()
        path = state_path()
        doc = _read_document(path) or _blank_document(reason=REASON_DEFAULT_DENY)
        rows = doc.setdefault("strategies", {})
        now = _utc_now()
        rows[name] = {
            "active": False,
            "authorised_for_live": False,
            "disable_reason": REASON_EVOLVE,
            "changed_at_utc": now,
            "sample_count": int(sample_count),
            "sharpe": float(sharpe),
            "loaded_from_durable": True,
        }
        from forex_bot.strategy_meta import strategies

        strat = strategies.get(name)
        if strat is not None:
            strat.active = False
            strat.authorised_for_live = False
            strat.disable_reason = REASON_EVOLVE
            strat.changed_at_utc = now
            strat.loaded_from_durable = True
        _snapshot_strategies_into(doc)
        _persist_unlocked(doc)


def operator_set_live_order_authorisation(
    *,
    state: str,
    reason: str,
    operator_confirmed: bool,
) -> None:
    """Explicit operator API. Not wired to HTTP or Telegram."""
    if not operator_confirmed:
        raise PermissionError("operator_confirmed=True is required")
    wanted = str(state or "").strip().upper()
    if wanted not in (AUTH_BLOCKED, AUTH_ALLOWED):
        raise ValueError("state must be BLOCKED or ALLOWED")
    why = (reason or "").strip()
    if not why:
        raise ValueError("reason is required")
    with _lock:
        if not _initialised:
            initialise_fail_closed()
        path = state_path()
        doc = _read_document(path) or _blank_document(reason=REASON_DEFAULT_DENY)
        global _effective_auth_state, _effective_auth_reason, _effective_auth_updated_at
        now = _utc_now()
        doc["live_order_authorisation"] = {
            "state": wanted,
            "reason": why,
            "updated_at_utc": now,
            "source": "operator",
        }
        _persist_unlocked(doc)
        _effective_auth_state = wanted
        _effective_auth_reason = why
        _effective_auth_updated_at = now


def operator_set_strategy_active(
    *,
    name: str,
    active: bool,
    reason: str,
    operator_confirmed: bool,
) -> None:
    """Explicit operator API. Not wired to HTTP or Telegram. Never called at startup."""
    if not operator_confirmed:
        raise PermissionError("operator_confirmed=True is required")
    key = (name or "").strip()
    if key not in KNOWN_STRATEGY_NAMES:
        raise ValueError(f"unknown strategy {name!r}")
    why = (reason or "").strip()
    if not why:
        raise ValueError("reason is required")
    with _lock:
        if not _initialised:
            initialise_fail_closed()
        from forex_bot.strategy_meta import strategies

        strat = strategies[key]
        strat.active = bool(active)
        strat.authorised_for_live = bool(active)
        strat.disable_reason = None if active else why
        strat.changed_at_utc = _utc_now()
        path = state_path()
        doc = _read_document(path) or _blank_document(reason=REASON_DEFAULT_DENY)
        _snapshot_strategies_into(doc)
        _persist_unlocked(doc)


def live_safety_snapshot() -> dict[str, Any]:
    """Read-only diagnostics. No credentials."""
    with _lock:
        from forex_bot.strategy_meta import strategies

        rows = []
        for name, strat in strategies.items():
            try:
                sharpe = float(strat.sharpe())
            except Exception:
                sharpe = None
            pnl = getattr(strat, "pnl", None)
            active = bool(getattr(strat, "active", False))
            authorised = bool(getattr(strat, "authorised_for_live", False))
            rows.append(
                {
                    "name": name,
                    "active": active,
                    "pnl_n": len(pnl) if pnl is not None else 0,
                    "sharpe": sharpe,
                    "disable_reason": getattr(strat, "disable_reason", None),
                    "changed_at_utc": getattr(strat, "changed_at_utc", None),
                    "loaded_from_durable": bool(getattr(strat, "loaded_from_durable", False)),
                    "authorised_for_live": authorised,
                }
            )
        block = live_open_blocked_reason()
        return {
            "live_order_authorisation": live_order_auth_state(),
            "live_order_authorisation_reason": live_order_auth_reason(),
            "live_order_authorisation_updated_at_utc": _effective_auth_updated_at,
            "effective_runtime_authorisation": live_order_auth_state(),
            "effective_runtime_authorisation_reason": live_order_auth_reason(),
            "persisted_authorisation": persisted_live_order_auth_state(),
            "persisted_authorisation_reason": persisted_live_order_auth_reason(),
            "persisted_authorisation_updated_at_utc": _persisted_auth_updated_at,
            "live_order_blocked_reason": block,
            "strategy_state_initialised": bool(_initialised),
            "strategy_state_valid": bool(_state_valid),
            "strategy_state_loaded_from_durable": bool(_loaded_from_durable),
            "strategy_state_path": str(state_path()),
            "strategies": rows,
        }


def _refuse_unless_pytest() -> None:
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        raise RuntimeError("live safety test helper refused outside pytest")


def reset_live_safety_for_tests() -> None:
    """Test helper: in-memory default deny. Does not write unless initialise is called."""
    _refuse_unless_pytest()
    global _initialised, _state_valid, _loaded_from_durable
    global _effective_auth_state, _effective_auth_reason, _effective_auth_updated_at
    global _persisted_auth_state, _persisted_auth_reason, _persisted_auth_updated_at
    with _lock:
        _initialised = False
        _state_valid = False
        _effective_auth_state = AUTH_BLOCKED
        _effective_auth_reason = REASON_PROCESS_START
        _effective_auth_updated_at = None
        _persisted_auth_state = AUTH_BLOCKED
        _persisted_auth_reason = REASON_DEFAULT_DENY
        _persisted_auth_updated_at = None
        _loaded_from_durable = False


def restore_strategy_runtime_defaults_for_tests() -> None:
    """Restore in-RAM strategy flags after fail-closed tests. Does not persist or authorise."""
    _refuse_unless_pytest()
    from forex_bot.strategy_meta import strategies

    for strat in strategies.values():
        strat.active = True
        strat.disable_reason = None
        strat.changed_at_utc = None
        strat.loaded_from_durable = False
        strat.authorised_for_live = False

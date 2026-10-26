"""Account-level execution limits for the shared evaluate path.

The three limits are explicit configuration. An unset, disabled, malformed,
or non-finite limit blocks. This module does not supply a production
threshold and does not read broker credentials.
"""

from __future__ import annotations

import json
import math
import os
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = 1
_LOCK = threading.Lock()
_LIMITS = (
    ("RISK_MAX_DAILY_LOSS_PCT", "daily_loss"),
    ("RISK_MAX_DRAWDOWN_PCT", "drawdown"),
    ("RISK_MAX_TOTAL_EXPOSURE_PCT", "exposure"),
)
_DISABLED = {"0", "0.0", "off", "disabled", "false", "none"}
_OUTSTANDING = {"PENDING", "PARTIAL", "UNRESOLVED"}
_ATTESTED = {"synthetic_offline", "verified"}


def _fraction(name: str, label: str) -> tuple[str | None, float | None]:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return f"{label}_limit_unconfigured", None
    text = str(raw).strip().lower()
    if text in _DISABLED:
        return f"{label}_limit_disabled", None
    try:
        value = float(text)
    except ValueError:
        return f"{label}_limit_malformed", None
    if not math.isfinite(value):
        return f"{label}_limit_nonfinite", None
    if value <= 0:
        return f"{label}_limit_invalid", None
    return None, value


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _state_path() -> tuple[str | None, Path | None]:
    raw = (os.getenv("RISK_STATE_PATH") or "").strip()
    if not raw:
        return "risk_state_unconfigured", None
    return None, Path(raw)


def _load(path: Path) -> tuple[str | None, dict[str, Any] | None]:
    if not path.is_file():
        return "risk_state_missing", None
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return "risk_state_unreadable", None
    if not isinstance(blob, dict) or int(blob.get("schema_version") or 0) != SCHEMA_VERSION:
        return "risk_state_malformed", None
    peak = _finite(blob.get("peak_equity"))
    baselines = blob.get("day_baselines")
    realised = blob.get("realised_by_day")
    if peak is None or peak <= 0 or not isinstance(baselines, dict) or not isinstance(realised, dict):
        return "risk_state_inconsistent", None
    return None, blob


def _attested(doc: dict[str, Any]) -> bool:
    recon = doc.get("reconciliation")
    account_id = str(doc.get("account_id") or "")
    currency = str(doc.get("currency") or "")
    if not isinstance(recon, dict) or recon.get("status") not in _ATTESTED:
        return False
    if not account_id or not currency:
        return False
    return recon.get("account_id") == account_id and recon.get("currency") == currency


@contextmanager
def exclusive_state(path: Path) -> Iterator[str | None]:
    """Hold an exclusive lock for one state file. A held lock fails closed."""
    lock_path = path.with_suffix(path.suffix + ".lock")
    handle: int | None = None
    try:
        handle = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
    except FileExistsError:
        yield "risk_state_contention"
        return
    except OSError:
        yield "durable_state_failed"
        return
    try:
        yield None
    finally:
        if handle is not None:
            os.close(handle)
        for _attempt in range(3):
            try:
                os.remove(lock_path)
                break
            except OSError:
                continue


def _save(path: Path, doc: dict[str, Any]) -> str | None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        payload = json.dumps(doc, indent=2, sort_keys=True)
        for _attempt in range(3):
            try:
                temporary.write_text(payload, encoding="utf-8")
                descriptor = os.open(temporary, os.O_RDWR)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                os.replace(temporary, path)
                return None
            except OSError:
                continue
    except OSError:
        return "risk_state_unreadable"
    return "risk_state_unreadable"


def load_offline_harness(stage: Path) -> None:
    """Seed the isolated offline test book. Production defaults stay unset."""
    import importlib.util

    harness = Path(__file__).resolve().parents[1] / "tests" / "r25_risk_harness.py"
    spec = importlib.util.spec_from_file_location("r25_risk_harness", harness)
    if spec is None or spec.loader is None:
        raise RuntimeError("r25 risk harness is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.install_synthetic_risk_context(stage)


def apply_realised_delta(day: str, delta: float, *, path: Path | None = None) -> str | None:
    """Add one realised amount to a UTC day. A missing book is not recreated."""
    reason, dest = _state_path()
    dest = path or dest
    if path is None and reason:
        return reason
    if dest is None:
        return "risk_state_unconfigured"
    amount = _finite(delta)
    if amount is None or not day:
        return "risk_state_inconsistent"
    with _LOCK:
        with exclusive_state(dest) as held:
            if held:
                return held
            loaded, doc = _load(dest)
            if loaded or doc is None:
                return loaded
            current = _finite((doc.get("realised_by_day") or {}).get(day))
            if current is None:
                return "daily_loss_baseline_missing"
            doc["realised_by_day"][day] = current + amount
            return _save(dest, doc)


def _exposure_notional(
    symbol: str, price: float
) -> tuple[str | None, float, set[str], set[str], dict[str, float]]:
    from forex_bot.orders import orders_by_client_id
    from forex_bot.positions import positions as posmap

    total = 0.0
    positioned: set[str] = set()
    order_ids: set[str] = set()
    by_symbol: dict[str, float] = {}
    for held_symbol, position in list(posmap.items()):
        units = _finite(getattr(position, "units", None))
        entry = _finite(getattr(position, "entry_price", None))
        if units is None or entry is None or units == 0 or entry <= 0:
            return "exposure_unreadable", 0.0, positioned, order_ids, by_symbol
        name = str(held_symbol).upper()
        notional = abs(units) * entry
        positioned.add(name)
        by_symbol[name] = notional
        total += notional
    for order in list(orders_by_client_id.values()):
        status = str(getattr(getattr(order, "status", None), "value", "") or "").upper()
        order_symbol = str(getattr(order, "symbol", "") or "").upper()
        order_ids.add(str(getattr(order, "client_order_id", "") or ""))
        if status == "FILLED" and order_symbol in positioned:
            continue
        if status not in _OUTSTANDING and status != "FILLED":
            continue
        units = _finite(getattr(order, "units_requested", None))
        order_price = _finite(getattr(order, "avg_fill_price", None))
        if units is None or order_price is None or units == 0 or order_price <= 0:
            return "exposure_unreadable", 0.0, positioned, order_ids, by_symbol
        total += abs(units) * order_price
    _ = symbol, price
    return None, total, positioned, order_ids, by_symbol


def _durable_exposure(
    doc: dict[str, Any],
    local_symbols: set[str],
    local_order_ids: set[str],
    local_notionals: dict[str, float],
) -> tuple[str | None, float]:
    positions = doc.get("exposure_positions", [])
    orders = doc.get("exposure_orders", [])
    if not isinstance(positions, list) or not isinstance(orders, list):
        return "exposure_unreadable", 0.0
    durable_symbols: set[str] = set()
    total = 0.0
    for position in positions:
        if not isinstance(position, dict):
            return "exposure_unreadable", 0.0
        name = str(position.get("symbol") or "").upper()
        notional = _finite(position.get("notional_account_ccy"))
        if not name or notional is None or notional < 0:
            return "exposure_unreadable", 0.0
        if name in local_symbols:
            if abs(local_notionals.get(name, 0.0) - notional) > 1e-4:
                return "exposure_book_inconsistent", 0.0
            continue
        durable_symbols.add(name)
        total += notional
    for order in orders:
        if not isinstance(order, dict):
            return "exposure_unreadable", 0.0
        order_id = str(order.get("id") or "")
        name = str(order.get("symbol") or "").upper()
        status = str(order.get("status") or "").upper()
        notional = _finite(order.get("notional_account_ccy"))
        if not order_id or not name or notional is None or notional < 0:
            return "exposure_unreadable", 0.0
        if order_id in local_order_ids:
            continue
        if status == "FILLED" and (name in durable_symbols or name in local_symbols):
            continue
        if status not in _OUTSTANDING and status != "FILLED":
            continue
        total += notional
    return None, total


def entry_risk_block(
    *,
    now: datetime | None,
    equity: float,
    unrealised: float | None,
    account_as_of: datetime | None,
    symbol: str,
    units: float,
    price: float,
) -> tuple[str | None, dict[str, float | None]]:
    """Return a block reason before reservation. None means the three limits pass."""
    details: dict[str, float | None] = {
        "existing_exposure": None,
        "proposed_exposure": None,
        "exposure_cap": None,
    }
    limits: dict[str, float] = {}
    for env_name, label in _LIMITS:
        reason, value = _fraction(env_name, label)
        if reason or value is None:
            return reason or f"{label}_limit_unconfigured", details
        limits[label] = value
    if account_as_of is None:
        return "account_snapshot_timestamp_missing", details
    upl = _finite(unrealised)
    if unrealised is None or upl is None:
        return "account_unrealised_unavailable", details
    equity_value = _finite(equity)
    if equity_value is None or equity_value <= 0:
        return "account_equity_invalid", details
    proposed = _finite(units)
    mark = _finite(price)
    if proposed is None or mark is None or proposed <= 0 or mark <= 0:
        return "exposure_unreadable", details
    proposed_notional = abs(proposed) * mark
    reason, existing, local_symbols, local_order_ids, local_notionals = _exposure_notional(symbol, mark)
    if reason:
        return reason, details
    cap = equity_value * limits["exposure"]
    details.update(
        {
            "existing_exposure": existing,
            "proposed_exposure": proposed_notional,
            "exposure_cap": cap,
        }
    )
    if not math.isfinite(cap) or cap <= 0:
        return "exposure_limit_invalid", details
    if existing + proposed_notional > cap + 1e-6:
        return "total_exposure_limit", details

    reason, dest = _state_path()
    if reason or dest is None:
        return reason or "risk_state_unconfigured", details
    if now is None:
        return "risk_state_inconsistent", details
    day = now.astimezone(timezone.utc).date().isoformat()
    with _LOCK:
        with exclusive_state(dest) as held:
            if held:
                return held, details
            loaded, doc = _load(dest)
            if loaded or doc is None:
                return loaded, details
            if not _attested(doc):
                return "account_unreconciled", details
            durable_reason, durable = _durable_exposure(doc, local_symbols, local_order_ids, local_notionals)
            if durable_reason:
                return durable_reason, details
            existing += durable
            details["existing_exposure"] = existing
            if existing + proposed_notional > cap + 1e-6:
                return "total_exposure_limit", details
            recon = doc.get("reconciliation") if isinstance(doc.get("reconciliation"), dict) else {}
            if recon.get("status") == "verified":
                quote = str(symbol).split("_")[-1].upper()
                if quote != str(doc.get("currency") or ""):
                    return "exposure_conversion_missing", details
            baselines = dict(doc.get("day_baselines") or {})
            realised_book = dict(doc.get("realised_by_day") or {})
            baseline = _finite(baselines.get(day))
            realised = _finite(realised_book.get(day))
            if baseline is None or baseline <= 0 or realised is None:
                return "daily_loss_baseline_missing", details
            peak = _finite(doc.get("peak_equity"))
            if peak is None or peak <= 0:
                return "drawdown_reference_missing", details
            if equity_value > peak:
                peak = equity_value
                doc["peak_equity"] = peak
                revision = doc.get("revision")
                if isinstance(revision, int) and not isinstance(revision, bool):
                    doc["revision"] = revision + 1
                saved = _save(dest, doc)
                if saved:
                    return saved, details
            daily_limit = limits["daily_loss"] * baseline
            if realised <= -daily_limit:
                return "daily_realised_loss_limit", details
            if realised + upl <= -daily_limit:
                return "daily_total_loss_limit", details
            drawdown = (peak - equity_value) / peak
            if drawdown >= limits["drawdown"]:
                return "max_drawdown_limit", details
    return None, details

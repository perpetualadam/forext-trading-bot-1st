"""Persist completed live M5 bid/ask candles for later V2 scoring. Observational only."""

from __future__ import annotations

import json
import logging
import math
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from forex_bot.v2_shadow.observe import v2_shadow_enabled
from forex_bot.v2_shadow.store import default_store_dir, redact_secrets

logger = logging.getLogger(__name__)

MARKET_SCHEMA_VERSION = "v2_shadow_market_m5_v1"
MARKET_DIR_NAME = "market"
GRANULARITY = "M5"
BAR_MINUTES = 5
SOURCE_LIVE_FETCH = "live_fetch_ohlcv"
REQUIRED_BA = (
    "bid_open",
    "bid_high",
    "bid_low",
    "bid_close",
    "ask_open",
    "ask_high",
    "ask_low",
    "ask_close",
)

_file_locks: dict[str, threading.Lock] = {}
_file_locks_guard = threading.Lock()
_known_keys: dict[str, set[str]] = {}
_known_loaded: set[str] = set()


def market_dir(store_dir: Path | None = None) -> Path:
    return (store_dir or default_store_dir()) / MARKET_DIR_NAME


def market_path(symbol: str, store_dir: Path | None = None, granularity: str = GRANULARITY) -> Path:
    sym = _norm_symbol(symbol)
    gran = str(granularity or GRANULARITY).upper()
    return market_dir(store_dir) / f"{sym}_{gran}.jsonl"


def _norm_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper().replace("-", "_").replace("/", "_")


def _file_lock(path: Path) -> threading.Lock:
    key = str(path)
    with _file_locks_guard:
        lock = _file_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _file_locks[key] = lock
        return lock


def _ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        dt = raw
    else:
        text = str(raw).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _canonical_start(raw: Any) -> str | None:
    dt = _ts(raw)
    if dt is None:
        return None
    return dt.replace(microsecond=0).isoformat()


def _f(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        x = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or x <= 0:
        return None
    return x


def _idempotency_key(symbol: str, granularity: str, candle_start_utc: str) -> str:
    return f"{_norm_symbol(symbol)}|{str(granularity).upper()}|{candle_start_utc}"


def _load_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    if not path.is_file():
        return keys
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            start = _canonical_start(row.get("candle_start_utc"))
            symbol = _norm_symbol(str(row.get("symbol") or ""))
            gran = str(row.get("granularity") or GRANULARITY).upper()
            if start and symbol:
                keys.add(_idempotency_key(symbol, gran, start))
    return keys


def _ensure_keys(path: Path) -> set[str]:
    key = str(path)
    if key not in _known_loaded:
        _known_keys[key] = _load_keys(path)
        _known_loaded.add(key)
    return _known_keys[key]


def reset_market_index_cache() -> None:
    """Test helper. Does not delete files."""
    _known_keys.clear()
    _known_loaded.clear()


def _ohlc_sane(o: float, h: float, l: float, c: float) -> bool:
    if h < l:
        return False
    if h < max(o, c):
        return False
    if l > min(o, c):
        return False
    return True


def candle_from_row(
    symbol: str,
    row: Any,
    *,
    now_utc: datetime | None = None,
    granularity: str = GRANULARITY,
    source: str = SOURCE_LIVE_FETCH,
) -> dict[str, Any] | None:
    """
    Build one persistable complete M5 bid/ask candle, or None if it must be skipped.

    Never synthesizes bid/ask from mid. Never accepts a forming or future bar.
    """
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    gran = str(granularity or GRANULARITY).upper()
    if gran != GRANULARITY:
        return None
    get = row.get if isinstance(row, dict) else row.__getitem__
    try:
        complete_raw = get("complete")
    except (KeyError, IndexError, TypeError, AttributeError):
        complete_raw = True
    if complete_raw is not None and str(complete_raw).strip().lower() in ("0", "false", "no", "f"):
        return None

    try:
        start_raw = get("time")
    except (KeyError, IndexError, TypeError, AttributeError):
        return None
    start = _ts(start_raw)
    if start is None:
        return None
    start = start.replace(microsecond=0)
    end = start + timedelta(minutes=BAR_MINUTES)
    if start > now or end > now:
        return None

    ba: dict[str, float] = {}
    for name in REQUIRED_BA:
        try:
            val = _f(get(name))
        except (KeyError, IndexError, TypeError, AttributeError):
            val = None
        if val is None:
            return None
        ba[name] = val
    if not _ohlc_sane(ba["bid_open"], ba["bid_high"], ba["bid_low"], ba["bid_close"]):
        return None
    if not _ohlc_sane(ba["ask_open"], ba["ask_high"], ba["ask_low"], ba["ask_close"]):
        return None
    if ba["ask_close"] < ba["bid_close"]:
        return None

    volume = None
    try:
        raw_vol = get("volume")
        if raw_vol is not None and str(raw_vol) != "":
            vol = float(raw_vol)
            if math.isfinite(vol) and vol >= 0:
                volume = vol
    except (KeyError, IndexError, TypeError, AttributeError, ValueError):
        volume = None

    recorded = now
    if recorded < end:
        return None

    return {
        "schema_version": MARKET_SCHEMA_VERSION,
        "symbol": _norm_symbol(symbol),
        "granularity": gran,
        "candle_start_utc": start.isoformat(),
        "candle_end_utc": end.isoformat(),
        "bid_open": ba["bid_open"],
        "bid_high": ba["bid_high"],
        "bid_low": ba["bid_low"],
        "bid_close": ba["bid_close"],
        "ask_open": ba["ask_open"],
        "ask_high": ba["ask_high"],
        "ask_low": ba["ask_low"],
        "ask_close": ba["ask_close"],
        "volume": volume,
        "complete": True,
        "recorded_at_utc": recorded.isoformat(),
        "source": source,
    }


def persist_completed_candle(candle: dict[str, Any], store_dir: Path | None = None) -> str:
    """
    Write one canonical row. Returns written / duplicate / rejected.
    Restart-safe: keys are reloaded from the JSONL.
    """
    if not candle or candle.get("complete") is not True:
        return "rejected"
    start = _canonical_start(candle.get("candle_start_utc"))
    symbol = _norm_symbol(str(candle.get("symbol") or ""))
    gran = str(candle.get("granularity") or GRANULARITY).upper()
    if not start or not symbol:
        return "rejected"
    end = _ts(candle.get("candle_end_utc"))
    recorded = _ts(candle.get("recorded_at_utc"))
    if end is None or recorded is None or recorded < end:
        return "rejected"
    path = market_path(symbol, store_dir, gran)
    ident = _idempotency_key(symbol, gran, start)
    lock = _file_lock(path)
    with lock:
        keys = _ensure_keys(path)
        if ident in keys:
            return "duplicate"
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(redact_secrets(candle), separators=(",", ":"), ensure_ascii=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        keys.add(ident)
    return "written"


def record_completed_m5_frame(
    symbol: str,
    frame: Any,
    *,
    store_dir: Path | None = None,
    now_utc: datetime | None = None,
    source: str = SOURCE_LIVE_FETCH,
) -> dict[str, int]:
    """Persist every valid complete BA candle in an already-fetched frame. No broker I/O."""
    counts = {
        "written": 0,
        "duplicate": 0,
        "skipped_forming": 0,
        "skipped_no_ba": 0,
        "skipped_malformed": 0,
        "rows_seen": 0,
    }
    if frame is None:
        return counts
    empty = getattr(frame, "empty", None)
    if empty is True:
        return counts
    try:
        rows = frame.to_dict("records")
    except Exception:
        try:
            rows = list(frame)
        except Exception:
            return counts
    now = now_utc or datetime.now(timezone.utc)
    for row in rows:
        counts["rows_seen"] += 1
        try:
            start = _ts(row.get("time") if isinstance(row, dict) else None)
            if start is not None and start + timedelta(minutes=BAR_MINUTES) > (
                now if now.tzinfo else now.replace(tzinfo=timezone.utc)
            ):
                counts["skipped_forming"] += 1
                continue
            candle = candle_from_row(symbol, row, now_utc=now, source=source)
            if candle is None:
                has_mid = False
                if isinstance(row, dict):
                    has_mid = row.get("close") is not None or row.get("open") is not None
                if has_mid and any(
                    _f(row.get(name) if isinstance(row, dict) else None) is None for name in REQUIRED_BA
                ):
                    counts["skipped_no_ba"] += 1
                else:
                    counts["skipped_malformed"] += 1
                continue
            status = persist_completed_candle(candle, store_dir=store_dir)
            counts[status] = counts.get(status, 0) + 1
        except Exception:
            counts["skipped_malformed"] += 1
    return counts


def maybe_record_completed_m5(
    symbol: str,
    frame: Any,
    *,
    store_dir: Path | None = None,
    now_utc: datetime | None = None,
    enabled: bool | None = None,
) -> dict[str, int] | None:
    """
    Research boundary. Never raises into the trading path.
    Additional OANDA requests: 0 (uses the already-fetched frame only).
    """
    try:
        if enabled is None:
            enabled = v2_shadow_enabled()
        if not enabled:
            return None
        counts = record_completed_m5_frame(symbol, frame, store_dir=store_dir, now_utc=now_utc)
        if counts.get("written"):
            logger.info(
                "[V2 SHADOW] market symbol=%s written=%s duplicate=%s skipped_no_ba=%s skipped_forming=%s",
                symbol,
                counts.get("written"),
                counts.get("duplicate"),
                counts.get("skipped_no_ba"),
                counts.get("skipped_forming"),
            )
        return counts
    except Exception:
        logger.exception("[V2 SHADOW] market persist failed (ignored)")
        return None

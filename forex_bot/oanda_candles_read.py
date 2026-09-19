"""Read-only OANDA InstrumentsCandles client for research downloads.

GET candles only. This module must never place or cancel orders.
It is intended for a *separate* CLI process, not the live bot loop.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

import pandas as pd

from forex_bot.decision_quality.history_cache import BAR_MINUTES, empty_frame, to_naive_utc
from forex_bot.oanda_rate_limit import acquire_oanda_rest_slot
from forex_bot.symbols import normalize_oanda_symbol

logger = logging.getLogger(__name__)

# Conservative extra pause after each candle GET. Does not change OANDA_MAX_REQUESTS_PER_SEC.
DEFAULT_HISTORY_CHUNK_DELAY_SEC = 0.6
HISTORY_PRICE = "MBA"  # mid + bid + ask when the endpoint supplies them


def _rfc3339(dt: datetime) -> str:
    naive = to_naive_utc(dt)
    return naive.strftime("%Y-%m-%dT%H:%M:%S.000000000Z")


def _candle_time(ts: str) -> datetime:
    p = pd.Timestamp(ts)
    if p.tzinfo is not None:
        p = p.tz_convert("UTC").tz_localize(None)
    return p.to_pydatetime()


def _side_ohlc(block: dict[str, Any] | None, prefix: str) -> dict[str, float | None]:
    if not block:
        return {f"{prefix}_{k}": None for k in ("open", "high", "low", "close")}
    return {
        f"{prefix}_open": float(block["o"]),
        f"{prefix}_high": float(block["h"]),
        f"{prefix}_low": float(block["l"]),
        f"{prefix}_close": float(block["c"]),
    }


def parse_candles_payload(
    data: dict[str, Any],
    *,
    now_utc: datetime | None = None,
    bar_minutes: int = BAR_MINUTES,
) -> pd.DataFrame:
    """Keep completed candles only. Mid OHLC is required; bid/ask optional."""
    now = to_naive_utc(now_utc or datetime.now(timezone.utc))
    width = max(1, int(bar_minutes))
    rows: list[dict[str, Any]] = []
    for c in data.get("candles") or []:
        if not c.get("complete", False):
            continue
        mid = c.get("mid") or {}
        if not mid:
            continue
        ts = _candle_time(str(c["time"]))
        # Forming / future bars are never stored.
        if ts + pd.Timedelta(minutes=width) > pd.Timestamp(now):
            continue
        vol = c.get("volume")
        try:
            volume = float(vol) if vol is not None and str(vol) != "" else None
        except (TypeError, ValueError):
            volume = None
        row = {
            "time": ts,
            "open": float(mid["o"]),
            "high": float(mid["h"]),
            "low": float(mid["l"]),
            "close": float(mid["c"]),
            "volume": volume,
            "complete": True,
        }
        row.update(_side_ohlc(c.get("bid"), "bid"))
        row.update(_side_ohlc(c.get("ask"), "ask"))
        rows.append(row)
    if not rows:
        return empty_frame()
    return pd.DataFrame(rows)


def request_candles_page(
    symbol: str,
    start: datetime,
    end: datetime,
    *,
    request_fn: Callable[[str, dict[str, str]], dict[str, Any]],
    now_utc: datetime | None = None,
    price: str = HISTORY_PRICE,
    granularity: str = "M5",
) -> pd.DataFrame:
    """
    One InstrumentsCandles-equivalent page via injected ``request_fn(instrument, params)``.
    Tests pass a mock; the CLI wires a real GET.
    Default granularity remains M5 (production/research M5 path unchanged).
    """
    gran = str(granularity or "M5").upper()
    width = 1 if gran == "M1" else BAR_MINUTES
    inst = normalize_oanda_symbol(symbol)
    params = {
        "granularity": gran,
        "from": _rfc3339(start),
        "to": _rfc3339(end),
        "price": price,
    }
    payload = request_fn(inst, params)
    return parse_candles_payload(payload, now_utc=now_utc, bar_minutes=width)


def live_instruments_candles_request(instrument: str, params: dict[str, str]) -> dict[str, Any]:
    """Sequential GET /v3/instruments/{instrument}/candles. No order endpoints."""
    import oandapyV20.endpoints.instruments as instruments

    from forex_bot.oanda_client import get_api

    api = get_api()
    if api is None:
        raise RuntimeError("OANDA API client unavailable (missing token?)")
    acquire_oanda_rest_slot()
    req = instruments.InstrumentsCandles(instrument=instrument, params=params)
    return api.request(req)


def paced_request(
    instrument: str,
    params: dict[str, str],
    *,
    request_fn: Callable[[str, dict[str, str]], dict[str, Any]] | None = None,
    chunk_delay_sec: float = DEFAULT_HISTORY_CHUNK_DELAY_SEC,
) -> dict[str, Any]:
    fn = request_fn or live_instruments_candles_request
    payload = fn(instrument, params)
    if chunk_delay_sec > 0:
        time.sleep(chunk_delay_sec)
    return payload

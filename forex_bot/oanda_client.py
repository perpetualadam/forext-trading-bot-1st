"""OANDA REST client (v20) for candles and runtime environment switch."""

from __future__ import annotations

import logging
import os
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import oandapyV20.endpoints.instruments as instruments
import pandas as pd
from oandapyV20 import API
from oandapyV20.exceptions import V20Error

from forex_bot.config import Config

logger = logging.getLogger(__name__)


def _format_oanda_error(exc: BaseException) -> str:
    """Log a short message; avoid dumping Cloudflare/OANDA HTML error pages."""
    if isinstance(exc, V20Error):
        body = (exc.msg or "").strip()
        if not body:
            return f"V20Error HTTP {exc.code}"
        low = body.lower()
        if "<html" in low or "<!doctype" in low or len(body) > 400:
            return (
                f"V20Error HTTP {exc.code} (HTML/long body omitted; "
                "often 502 = OANDA/Cloudflare outage — retry later)"
            )
        if exc.code == 401:
            return (
                f"V20Error HTTP 401: {body[:400]} "
                "(token must match TRADING_MODE: practice token for practice, live token for live)"
            )
        return f"V20Error HTTP {exc.code}: {body[:400]}"
    text = str(exc).strip()
    low = text.lower()
    if "<html" in low or len(text) > 500:
        return f"{type(exc).__name__}: non-JSON or long response ({len(text)} chars omitted)"
    return f"{type(exc).__name__}: {text[:500]}"

_api: API | None = None


def _environment() -> str:
    return "live" if Config.TRADING_MODE == "live" else "practice"


def build_api() -> API | None:
    """Create or replace the global API client for the current TRADING_MODE."""
    global _api
    token = (Config.OANDA_ACCESS_TOKEN or "").strip()
    if not token:
        logger.warning("OANDA_ACCESS_TOKEN missing; market data calls will fail.")
        _api = None
        return None
    _api = API(access_token=token, environment=_environment())
    return _api


def get_api() -> API | None:
    if _api is None:
        return build_api()
    return _api


_GRANULARITY_MINUTES: dict[str, int] = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D": 1440,
}


def _utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _to_oanda_rfc3339(dt: datetime) -> str:
    d = _utc_naive(dt)
    return d.strftime("%Y-%m-%dT%H:%M:%S.000000000Z")


def _candle_time_to_naive_utc(ts: str) -> datetime:
    p = pd.Timestamp(ts)
    if p.tzinfo is not None:
        p = p.tz_convert("UTC").tz_localize(None)
    return p.to_pydatetime()


def _chunk_delay_sec() -> float:
    """Pause between historical chunk requests. Backtests default to 0 to minimise OANDA load."""
    raw = (os.getenv("OANDA_CHUNK_DELAY_SEC") or "").strip()
    if raw:
        try:
            return max(0.0, min(float(raw), 5.0))
        except ValueError:
            return 0.1
    if os.getenv("FOREX_BACKTEST", "").strip().lower() in ("1", "true", "yes", "on"):
        return 0.0
    return 0.1


def _max_candles_per_request() -> int:
    raw = (os.getenv("OANDA_MAX_CANDLES_PER_REQUEST") or "").strip()
    if raw:
        try:
            return max(50, min(int(raw), 5000))
        except ValueError:
            pass
    if os.getenv("FOREX_BACKTEST", "").strip().lower() in ("1", "true", "yes", "on"):
        return 5000
    return 500


def _oanda_max_retries() -> int:
    try:
        v = int((os.getenv("OANDA_MAX_RETRIES") or "6").strip())
        return max(1, min(v, 20))
    except ValueError:
        return 6


def _is_transient_v20(exc: BaseException) -> bool:
    return isinstance(exc, V20Error) and exc.code in (429, 502, 503, 504)


def _oanda_request(api: API, request_obj: Any, *, context: str) -> dict:
    """REST call with exponential backoff on rate limit / gateway errors."""
    max_retries = _oanda_max_retries()
    delay = 0.5
    last_exc: BaseException | None = None
    for attempt in range(max_retries):
        try:
            return api.request(request_obj)
        except Exception as exc:
            last_exc = exc
            if _is_transient_v20(exc) and attempt < max_retries - 1:
                wait = min(delay + random.random() * 0.35, 35.0)
                logger.warning(
                    "OANDA %s: HTTP %s (%s/%s) — retry in %.1fs",
                    context,
                    exc.code,
                    attempt + 1,
                    max_retries,
                    wait,
                )
                time.sleep(wait)
                delay = min(delay * 2.0, 20.0)
                continue
            raise
    assert last_exc is not None
    raise last_exc


def fetch_ohlcv_range(
    symbol: str,
    start: datetime,
    end: datetime,
    granularity: str = "M5",
    *,
    max_candles_per_request: int | None = None,
) -> pd.DataFrame | None:
    """
    Historical mid OHLCV between ``start`` and ``end`` (UTC), chunked for OANDA limits.

    Skips incomplete candles. Returns ``None`` if the API client is missing or all chunks fail.

    Between chunks: delay from ``OANDA_CHUNK_DELAY_SEC`` (unset + backtest → 0; live default 0.1s).
    Chunk size: ``OANDA_MAX_CANDLES_PER_REQUEST`` or 5000 in backtest / 500 live (OANDA cap 5000).
    """
    api = get_api()
    if api is None:
        return None
    mcp = max_candles_per_request if max_candles_per_request is not None else _max_candles_per_request()
    gran_mins = _GRANULARITY_MINUTES.get(granularity, 5)
    span_mins = max(1, gran_mins * (mcp - 1))
    chunk_delta = timedelta(minutes=span_mins)

    cur = _utc_naive(start)
    end_u = _utc_naive(end)
    if cur >= end_u:
        return None

    rows: list[dict[str, float | str]] = []
    safety = 0
    last_cur: datetime | None = None
    chunk_delay = _chunk_delay_sec()

    while cur < end_u and safety < 5000:
        safety += 1
        chunk_to = min(cur + chunk_delta, end_u)
        params = {
            "granularity": granularity,
            "from": _to_oanda_rfc3339(cur),
            "to": _to_oanda_rfc3339(chunk_to),
            "price": "M",
        }
        r = instruments.InstrumentsCandles(instrument=symbol, params=params)
        try:
            data = _oanda_request(api, r, context=f"range {symbol}")
        except Exception as exc:
            logger.error("OANDA range candles failed for %s: %s", symbol, _format_oanda_error(exc))
            return None

        candles = data.get("candles", [])
        if not candles:
            nxt = cur + timedelta(minutes=gran_mins)
            if last_cur is not None and nxt <= last_cur:
                break
            cur = nxt
            continue

        for c in candles:
            if not c.get("complete", True):
                continue
            mid = c.get("mid") or {}
            if not mid:
                continue
            rows.append(
                {
                    "time": c["time"],
                    "open": float(mid["o"]),
                    "high": float(mid["h"]),
                    "low": float(mid["l"]),
                    "close": float(mid["c"]),
                }
            )

        last_ts = _candle_time_to_naive_utc(candles[-1]["time"])
        nxt_cur = last_ts + timedelta(minutes=gran_mins)
        if last_cur is not None and nxt_cur <= last_cur:
            break
        last_cur = cur
        cur = nxt_cur
        if chunk_delay > 0:
            time.sleep(chunk_delay)

    if not rows:
        return None
    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["time"], keep="last").sort_values("time").reset_index(drop=True)
    return df


def fetch_ohlcv(
    symbol: str = "EUR_USD",
    granularity: str = "M5",
    count: int = 50,
) -> pd.DataFrame | None:
    api = get_api()
    if api is None:
        return None
    params = {"granularity": granularity, "count": count, "price": "M"}
    r = instruments.InstrumentsCandles(instrument=symbol, params=params)
    try:
        data = _oanda_request(api, r, context=f"latest {symbol}")
    except Exception as exc:
        logger.error("OANDA candles failed for %s: %s", symbol, _format_oanda_error(exc))
        return None
    ohlcv: list[dict[str, float | str]] = []
    for c in data.get("candles", []):
        if not c.get("complete", True):
            continue
        mid = c.get("mid") or {}
        ohlcv.append(
            {
                "time": c["time"],
                "open": float(mid["o"]),
                "high": float(mid["h"]),
                "low": float(mid["l"]),
                "close": float(mid["c"]),
            }
        )
    if not ohlcv:
        return None
    return pd.DataFrame(ohlcv)

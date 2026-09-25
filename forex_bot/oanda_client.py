"""OANDA REST client (v20) for candles and runtime environment switch."""

from __future__ import annotations

import logging
import math
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
    from forex_bot.log_redact import redact_log_text

    if isinstance(exc, V20Error):
        body = (exc.msg or "").strip()
        if not body:
            return redact_log_text(f"V20Error HTTP {exc.code}")
        low = body.lower()
        if "<html" in low or "<!doctype" in low or len(body) > 400:
            return redact_log_text(
                f"V20Error HTTP {exc.code} (HTML/long body omitted; "
                "often 502 = OANDA/Cloudflare outage — retry later)"
            )
        if exc.code == 401:
            return redact_log_text(
                f"V20Error HTTP 401: {body[:400]} "
                "(token must match TRADING_MODE: practice token for practice, live token for live)"
            )
        return redact_log_text(f"V20Error HTTP {exc.code}: {body[:400]}")
    text = str(exc).strip()
    low = text.lower()
    if "<html" in low or len(text) > 500:
        return f"{type(exc).__name__}: non-JSON or long response ({len(text)} chars omitted)"
    return redact_log_text(f"{type(exc).__name__}: {text[:500]}")

_api: API | None = None

# Last GET /v3/accounts/{id}/summary (OANDA AccountSummary).
_account_summary: dict[str, Any] = {}


def _environment() -> str:
    """oandapyV20 env key; maps to official hosts in TRADING_ENVIRONMENTS."""
    return "live" if Config.TRADING_MODE == "live" else "practice"


def official_rest_host() -> str:
    """Development Guide REST hosts: fxTrade vs fxTrade Practice."""
    if _environment() == "live":
        return "https://api-fxtrade.oanda.com"
    return "https://api-fxpractice.oanda.com"


def official_env_label() -> str:
    return "fxTrade" if _environment() == "live" else "fxTrade Practice"


def oanda_instrument(symbol: str) -> str:
    """InstrumentName: BASE_QUOTE with an underscore (EUR_USD), not hyphen or slash."""
    from forex_bot.symbols import normalize_oanda_symbol

    return normalize_oanda_symbol(symbol)


def _env_timeout_sec(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return max(0.1, float(raw))
    except ValueError:
        return default


def oanda_http_timeout() -> tuple[float, float]:
    """``(connect, read)`` seconds for every OANDA REST call. Never leave these unset."""
    connect = _env_timeout_sec("OANDA_CONNECT_TIMEOUT_SEC", 15.0)
    read = _env_timeout_sec("OANDA_HTTP_TIMEOUT_SEC", 15.0)
    return (connect, read)


def _apply_http_timeout(api: API) -> API:
    """Keep request_params.timeout on an existing client (shared Session has no default)."""
    timeout = oanda_http_timeout()
    params = dict(getattr(api, "_request_params", None) or {})
    params["timeout"] = timeout
    api._request_params = params
    return api


def build_api() -> API | None:
    """Create or replace the global API client for the current TRADING_MODE."""
    global _api
    token = (Config.OANDA_ACCESS_TOKEN or "").strip()
    if not token:
        logger.warning("OANDA_ACCESS_TOKEN missing; market data calls will fail.")
        _api = None
        return None
    # Official: Authorization Bearer (library) + Accept-Datetime-Format RFC3339.
    # request_params.timeout is required: oandapyV20/requests otherwise wait forever.
    _api = API(
        access_token=token,
        environment=_environment(),
        headers={"Accept-Datetime-Format": "RFC3339"},
        request_params={"timeout": oanda_http_timeout()},
    )
    logger.info(
        "OANDA REST client %s %s timeout=%s (token matches this host only)",
        official_env_label(),
        official_rest_host(),
        oanda_http_timeout(),
    )
    return _api


def get_api() -> API | None:
    if _api is None:
        return build_api()
    return _apply_http_timeout(_api)


def last_account_summary() -> dict[str, Any]:
    """Cached AccountSummary fields (NAV, balance, currency, marginAvailable, host)."""
    return dict(_account_summary)


def fetch_account_summary() -> dict[str, Any] | None:
    """
    GET /v3/accounts/{accountID}/summary — official AccountSummary.

    NAV and currency are the broker-truth equity for sizing (account CCY, e.g. GBP).
    """
    import oandapyV20.endpoints.accounts as accounts

    from forex_bot.state import set_broker_account

    api = get_api()
    aid = (Config.OANDA_ACCOUNT_ID or os.getenv("OANDA_ACCOUNT_ID") or "").strip()
    if api is None or not aid:
        return None
    r = accounts.AccountSummary(accountID=aid)
    try:
        data = _oanda_request(api, r, context="account summary")
    except Exception as exc:
        logger.error("OANDA AccountSummary failed: %s", _format_oanda_error(exc))
        return None
    acct = data.get("account") if isinstance(data, dict) else None
    if not isinstance(acct, dict):
        return None
    try:
        nav = float(str(acct.get("NAV") or acct.get("balance") or "0").replace(",", ""))
    except (TypeError, ValueError):
        nav = 0.0
    try:
        balance = float(str(acct.get("balance") or "0").replace(",", ""))
    except (TypeError, ValueError):
        balance = nav
    try:
        margin_av = float(str(acct.get("marginAvailable") or "0").replace(",", ""))
    except (TypeError, ValueError):
        margin_av = 0.0
    currency = str(acct.get("currency") or "").strip().upper()
    snap = {
        "id": str(acct.get("id") or aid),
        "NAV": nav,
        "balance": balance,
        "currency": currency,
        "marginAvailable": margin_av,
        "alias": str(acct.get("alias") or ""),
        "host": official_rest_host(),
        "environment": official_env_label(),
    }
    _account_summary.clear()
    _account_summary.update(snap)
    set_broker_account(nav, currency)
    logger.info(
        "[OANDA ACCOUNT] %s NAV=%.2f %s balance=%.2f marginAvailable=%.2f host=%s",
        official_env_label(),
        nav,
        currency or "?",
        balance,
        margin_av,
        official_rest_host(),
    )
    return snap


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


def _is_transient_transport(exc: BaseException) -> bool:
    """Dropped TLS / connection blips (e.g. SSLEOFError) — safe to retry GETs."""
    seen: set[int] = set()
    cur: BaseException | None = exc
    needles = (
        "ssleoferror",
        "sslerror",
        "unexpected_eof",
        "eof occurred in violation of protocol",
        "max retries exceeded",
        "connection reset",
        "connection aborted",
        "read timed out",
        "connect timeout",
        "temporarily unavailable",
    )
    names = ("sslerror", "ssleoferror", "connectionerror", "timeout", "protocolerror")
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if any(n in type(cur).__name__.lower() for n in names):
            return True
        text = str(cur).lower()
        if any(n in text for n in needles):
            return True
        cur = cur.__cause__ or getattr(cur, "__context__", None)
    return False


def _oanda_request(api: API, request_obj: Any, *, context: str) -> dict:
    """REST call with exponential backoff on rate limit / gateway / TLS drops."""
    max_retries = _oanda_max_retries()
    delay = 0.5
    last_exc: BaseException | None = None
    for attempt in range(max_retries):
        try:
            from forex_bot.oanda_rate_limit import acquire_oanda_rest_slot

            acquire_oanda_rest_slot()
            return api.request(request_obj)
        except Exception as exc:
            last_exc = exc
            transient = _is_transient_v20(exc) or _is_transient_transport(exc)
            if transient and attempt < max_retries - 1:
                wait = min(delay + random.random() * 0.35, 35.0)
                code = getattr(exc, "code", type(exc).__name__)
                logger.warning(
                    "OANDA %s: %s (%s/%s) — retry in %.1fs",
                    context,
                    code,
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
        r = instruments.InstrumentsCandles(instrument=oanda_instrument(symbol), params=params)
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


def _optional_price(block: dict[str, Any] | None, key: str) -> float | None:
    if not block:
        return None
    try:
        return float(block[key])
    except (KeyError, TypeError, ValueError):
        return None


def fetch_ohlcv(
    symbol: str = "EUR_USD",
    granularity: str = "M5",
    count: int = 50,
) -> pd.DataFrame | None:
    """
    Latest completed candles. One InstrumentsCandles GET.

    Mid OHLC columns (open/high/low/close) are unchanged for trading.
    When the same payload includes bid/ask, those columns are retained for
    research persistence. Incomplete/forming candles are dropped.
    """
    api = get_api()
    if api is None:
        return None
    inst = oanda_instrument(symbol)
    # Same request count as price=M. MBA adds bid/ask buckets on the payload.
    params = {"granularity": granularity, "count": count, "price": "MBA"}
    r = instruments.InstrumentsCandles(instrument=inst, params=params)
    try:
        data = _oanda_request(api, r, context=f"latest {inst}")
    except Exception as exc:
        logger.error("OANDA candles failed for %s: %s", inst, _format_oanda_error(exc))
        return None
    ohlcv: list[dict[str, float | str | bool | None]] = []
    for c in data.get("candles", []):
        if not c.get("complete", True):
            continue
        mid = c.get("mid") or {}
        if not mid:
            continue
        try:
            row: dict[str, float | str | bool | None] = {
                "time": c["time"],
                "open": float(mid["o"]),
                "high": float(mid["h"]),
                "low": float(mid["l"]),
                "close": float(mid["c"]),
                "complete": True,
            }
        except (KeyError, TypeError, ValueError):
            continue
        bid = c.get("bid") or {}
        ask = c.get("ask") or {}
        row["bid_open"] = _optional_price(bid, "o")
        row["bid_high"] = _optional_price(bid, "h")
        row["bid_low"] = _optional_price(bid, "l")
        row["bid_close"] = _optional_price(bid, "c")
        row["ask_open"] = _optional_price(ask, "o")
        row["ask_high"] = _optional_price(ask, "h")
        row["ask_low"] = _optional_price(ask, "l")
        row["ask_close"] = _optional_price(ask, "c")
        vol = c.get("volume")
        try:
            row["volume"] = float(vol) if vol is not None and str(vol) != "" else None
        except (TypeError, ValueError):
            row["volume"] = None
        ohlcv.append(row)
    if not ohlcv:
        return None
    return pd.DataFrame(ohlcv)


def _parse_pricing_px(raw: Any) -> float | None:
    if raw in (None, ""):
        return None
    try:
        px = float(str(raw).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(px) or px <= 0:
        return None
    return px


def fetch_pricing_snapshot(
    symbols: list[str] | tuple[str, ...] | None = None,
    *,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """
    GET /v3/accounts/{id}/pricing for the given instruments in one request.

    Returns ``instrument -> ManageQuote``. Empty dict if unavailable. Never writes.
    Manage-path callers keep the default (swallow errors). Entry geometry uses
    ``raise_on_error=True`` so a failed GET is fail-closed as a request failure.
    """
    from forex_bot.live_manage import ManageQuote
    from forex_bot.profit_protection import _to_epoch
    from forex_bot.symbols import DEFAULT_FOREX_SYMBOLS

    api = get_api()
    aid = (Config.OANDA_ACCOUNT_ID or os.getenv("OANDA_ACCOUNT_ID") or "").strip()
    if api is None or not aid:
        if raise_on_error:
            raise RuntimeError("OANDA API client unavailable for PricingInfo")
        return {}
    raw_syms = list(symbols) if symbols else list(DEFAULT_FOREX_SYMBOLS)
    insts: list[str] = []
    seen: set[str] = set()
    for s in raw_syms:
        inst = oanda_instrument(s)
        if inst and inst not in seen:
            seen.add(inst)
            insts.append(inst)
    if not insts:
        return {}
    try:
        import oandapyV20.endpoints.pricing as pricing
    except ImportError:
        logger.warning("oandapyV20 pricing endpoint unavailable")
        if raise_on_error:
            raise
        return {}
    r = pricing.PricingInfo(accountID=aid, params={"instruments": ",".join(insts)})
    try:
        data = _oanda_request(api, r, context="pricing snapshot")
    except Exception as exc:
        logger.error("OANDA PricingInfo failed: %s", _format_oanda_error(exc))
        if raise_on_error:
            raise
        return {}
    out: dict[str, ManageQuote] = {}
    for p in data.get("prices") or []:
        if not isinstance(p, dict):
            continue
        inst = oanda_instrument(str(p.get("instrument") or ""))
        if not inst:
            continue
        bids = p.get("bids") or []
        asks = p.get("asks") or []
        bid0 = bids[0].get("price") if bids and isinstance(bids[0], dict) else None
        ask0 = asks[0].get("price") if asks and isinstance(asks[0], dict) else None
        status = str(p.get("status") or "").strip().lower()
        tradeable_flag = p.get("tradeable")
        if tradeable_flag is None:
            tradeable = status not in ("non-tradeable", "nontradeable", "invalid")
        else:
            tradeable = bool(tradeable_flag)
        out[inst] = ManageQuote(
            instrument=inst,
            bid=_parse_pricing_px(bid0),
            ask=_parse_pricing_px(ask0),
            closeout_bid=_parse_pricing_px(p.get("closeoutBid")),
            closeout_ask=_parse_pricing_px(p.get("closeoutAsk")),
            time_epoch=_to_epoch(p.get("time")),
            tradeable=tradeable,
        )
    return out

"""OANDA REST client (v20) for candles and runtime environment switch."""

from __future__ import annotations

import logging
import oandapyV20.endpoints.instruments as instruments
import pandas as pd
from oandapyV20 import API

from forex_bot.config import Config

logger = logging.getLogger(__name__)

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
        data = api.request(r)
    except Exception as exc:
        logger.error("OANDA candles failed for %s: %s", symbol, exc)
        return None
    ohlcv: list[dict[str, float | str]] = []
    for c in data.get("candles", []):
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

"""OANDA v20 market execution (optional; broker-agnostic fallbacks in trading.py)."""

from __future__ import annotations

import asyncio
import logging
import math
import os
from typing import Any

import oandapyV20.endpoints.orders as oanda_orders

from forex_bot.config import Config
from forex_bot.oanda_client import get_api

logger = logging.getLogger(__name__)


def use_oanda_live() -> bool:
    """
    True when broker orders are allowed.

    - If ``EXECUTION_MODE`` is set to ``paper_broker`` or ``live_broker``, orders are enabled.
    - If unset, legacy ``USE_OANDA_LIVE`` gates order placement (``paper`` mode never sends orders).
    """
    from forex_bot.execution import ExecutionMode, get_execution_mode

    if (os.getenv("EXECUTION_MODE") or "").strip():
        return get_execution_mode() != ExecutionMode.PAPER
    raw = (os.getenv("USE_OANDA_LIVE") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _access_token() -> str:
    return (os.getenv("OANDA_ACCESS_TOKEN") or os.getenv("OANDA_API_KEY") or "").strip()


def _account_id() -> str:
    return (Config.OANDA_ACCOUNT_ID or os.getenv("OANDA_ACCOUNT_ID") or "").strip()


def _order_units_for_close(position_units: float, position_direction: str) -> int:
    """OANDA: positive = long, negative = short. Closing long → negative units."""
    u = max(1, int(round(abs(float(position_units)))))
    if (position_direction or "").upper().strip() == "BUY":
        return -u
    return u


def _parse_fill(response: dict[str, Any]) -> tuple[float, float]:
    """Return (realized_pl_account_ccy, fill_price) from OrderCreate response."""
    oft = response.get("orderFillTransaction")
    if not oft:
        raise ValueError("OANDA response missing orderFillTransaction")

    fill_price = float(str(oft.get("price", "0")).replace(",", ""))
    pl_raw = oft.get("pl")
    if pl_raw is None or str(pl_raw).strip() == "":
        pl = float("nan")
    else:
        pl = float(str(pl_raw).replace(",", ""))
    return pl, fill_price


def _place_market_order_sync(symbol: str, position_units: float, position_direction: str) -> tuple[float, float]:
    api = get_api()
    if api is None:
        raise RuntimeError("OANDA API client unavailable (token / build_api)")

    account_id = _account_id()
    if not account_id:
        raise RuntimeError("OANDA_ACCOUNT_ID missing")

    instrument = symbol.upper().strip()
    units_int = _order_units_for_close(position_units, position_direction)

    body: dict[str, Any] = {
        "order": {
            "type": "MARKET",
            "instrument": instrument,
            "units": str(units_int),
            "timeInForce": "FOK",
            "positionFill": "DEFAULT",
        }
    }

    r = oanda_orders.OrderCreate(accountID=account_id, data=body)
    try:
        response = api.request(r)
    except Exception as exc:
        logger.error("OANDA OrderCreate failed: %s", exc)
        raise RuntimeError(str(exc)) from exc

    pl, fill_price = _parse_fill(response if isinstance(response, dict) else {})
    if math.isnan(pl):
        logger.warning("OANDA fill missing pl; fill_price=%s", fill_price)
    return pl, fill_price


async def execute_oanda_market_close(
    symbol: str,
    position_units: float,
    position_direction: str,
    entry_price: float,
) -> tuple[float, float]:
    """
    Place a market order to flatten ``position_units`` / ``position_direction``.

    Returns ``(realized_pnl_account_currency, exit_fill_price)``.
    Runs the synchronous REST call in a thread pool.
    """
    if not use_oanda_live():
        raise RuntimeError("USE_OANDA_LIVE is not enabled")

    if not _access_token():
        raise RuntimeError("OANDA_ACCESS_TOKEN or OANDA_API_KEY missing")

    pl, fill_price = await asyncio.to_thread(
        _place_market_order_sync, symbol, position_units, position_direction
    )
    if math.isnan(pl):
        u = abs(float(position_units))
        d = (position_direction or "").upper().strip()
        if d == "BUY":
            pl = (fill_price - float(entry_price)) * u
        else:
            pl = (float(entry_price) - fill_price) * u
    return float(pl), float(fill_price)

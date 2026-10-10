"""Independent simulator-accounting fixtures. Not trading-performance evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from forex_bot.research.adaptive_ensemble.conversion import (
    ConversionResult,
    RateTable,
    convert_pnl,
)
from forex_bot.research.adaptive_ensemble.simulate import fill_price, mark_exit


def _bar(
    ts: str,
    o: float,
    h: float,
    l: float,
    c: float,
    spread: float,
) -> dict[str, Any]:
    half = spread / 2.0
    return {
        "time": ts,
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "bid_open": o - half,
        "ask_open": o + half,
        "bid_high": h - half,
        "ask_high": h + half,
        "bid_low": l - half,
        "ask_low": l + half,
        "bid_close": c - half,
        "ask_close": c + half,
        "feat_atr": 0.0004,
    }


def eur_usd_long_fixture() -> dict[str, Any]:
    """Buy next-bar ask 1.10012, exit bid 1.10112, units 1000 → +1.0 USD."""
    rows = [
        _bar("2026-09-01T12:00:00Z", 1.10000, 1.10020, 1.09980, 1.10000, 0.00024),
        _bar("2026-09-01T12:05:00Z", 1.10000, 1.10030, 1.09990, 1.10020, 0.00024),
        _bar("2026-09-01T12:10:00Z", 1.10020, 1.10120, 1.10010, 1.10112, 0.00000),
    ]
    # Force exact executable prices on the fill/exit bars.
    rows[1]["ask_open"] = 1.10012
    rows[2]["bid_close"] = 1.10112
    rows[2]["low"] = 1.10010
    rows[2]["high"] = 1.10120
    df = pd.DataFrame(rows)
    entry = fill_price(df, 1, "BUY", "base")
    exit_i, exit_px, why = mark_exit(df, 2, "BUY", float(entry or 0), 1.09, 1.20, 24)
    units = 1000.0
    pnl_q = (exit_px - float(entry or 0)) * units
    return {
        "name": "eur_usd_long",
        "pair": "EUR_USD",
        "direction": "BUY",
        "entry": entry,
        "exit_px": exit_px,
        "exit_i": exit_i,
        "why": why,
        "pnl_quote": pnl_q,
        "expected_entry": 1.10012,
        "expected_exit": 1.10112,
        "expected_pnl_quote": 1.0,
    }


def eur_usd_short_fixture() -> dict[str, Any]:
    rows = [
        _bar("2026-09-01T12:00:00Z", 1.10000, 1.10020, 1.09980, 1.10000, 0.00024),
        _bar("2026-09-01T12:05:00Z", 1.10000, 1.10030, 1.09970, 1.09980, 0.00024),
        _bar("2026-09-01T12:10:00Z", 1.09980, 1.09990, 1.09880, 1.09888, 0.00000),
    ]
    rows[1]["bid_open"] = 1.09988
    rows[2]["ask_close"] = 1.09888
    df = pd.DataFrame(rows)
    entry = fill_price(df, 1, "SELL", "base")
    exit_i, exit_px, why = mark_exit(df, 2, "SELL", float(entry or 0), 1.12, 1.09, 24)
    pnl_q = (float(entry or 0) - exit_px) * 1000.0
    return {
        "name": "eur_usd_short",
        "pair": "EUR_USD",
        "direction": "SELL",
        "entry": entry,
        "exit_px": exit_px,
        "pnl_quote": pnl_q,
        "expected_entry": 1.09988,
        "expected_exit": 1.09888,
        "expected_pnl_quote": 1.0,
        "why": why,
        "exit_i": exit_i,
    }


def usd_jpy_long_fixture() -> dict[str, Any]:
    rows = [
        _bar("2026-09-01T12:00:00Z", 150.00, 150.10, 149.90, 150.00, 0.02),
        _bar("2026-09-01T12:05:00Z", 150.00, 150.20, 149.95, 150.10, 0.02),
        _bar("2026-09-01T12:10:00Z", 150.10, 150.30, 150.05, 150.20, 0.00),
    ]
    rows[1]["ask_open"] = 150.02
    rows[2]["bid_close"] = 150.12
    for r in rows:
        r["feat_atr"] = 0.08
    df = pd.DataFrame(rows)
    entry = fill_price(df, 1, "BUY", "base")
    exit_i, exit_px, why = mark_exit(df, 2, "BUY", float(entry or 0), 149.0, 151.0, 24)
    pnl_q = (exit_px - float(entry or 0)) * 1000.0
    return {
        "name": "usd_jpy_long",
        "pair": "USD_JPY",
        "entry": entry,
        "exit_px": exit_px,
        "pnl_quote": pnl_q,
        "expected_entry": 150.02,
        "expected_exit": 150.12,
        "expected_pnl_quote": 100.0,
        "why": why,
        "exit_i": exit_i,
    }


def usd_jpy_short_fixture() -> dict[str, Any]:
    rows = [
        _bar("2026-09-01T12:00:00Z", 150.00, 150.10, 149.90, 150.00, 0.02),
        _bar("2026-09-01T12:05:00Z", 150.00, 150.05, 149.80, 149.90, 0.02),
        _bar("2026-09-01T12:10:00Z", 149.90, 149.95, 149.70, 149.80, 0.00),
    ]
    rows[1]["bid_open"] = 149.98
    rows[2]["ask_close"] = 149.88
    for r in rows:
        r["feat_atr"] = 0.08
    df = pd.DataFrame(rows)
    entry = fill_price(df, 1, "SELL", "base")
    exit_i, exit_px, why = mark_exit(df, 2, "SELL", float(entry or 0), 151.0, 149.0, 24)
    pnl_q = (float(entry or 0) - exit_px) * 1000.0
    return {
        "name": "usd_jpy_short",
        "pair": "USD_JPY",
        "entry": entry,
        "exit_px": exit_px,
        "pnl_quote": pnl_q,
        "expected_entry": 149.98,
        "expected_exit": 149.88,
        "expected_pnl_quote": 100.0,
        "why": why,
        "exit_i": exit_i,
    }


def same_bar_ambiguity_fixture() -> dict[str, Any]:
    rows = [
        _bar("2026-09-01T12:00:00Z", 1.10, 1.101, 1.099, 1.10, 0.0002),
        _bar("2026-09-01T12:05:00Z", 1.10, 1.101, 1.099, 1.10, 0.0002),
        _bar("2026-09-01T12:10:00Z", 1.10, 1.12, 1.08, 1.10, 0.0002),
    ]
    df = pd.DataFrame(rows)
    entry = 1.10
    sl, tp = 1.09, 1.11
    _exit_i, exit_px, why = mark_exit(df, 2, "BUY", entry, sl, tp, 24)
    return {"why": why, "exit_px": exit_px, "expected_why": "ambiguous_same_bar_conservative_sl", "expected_px": sl}


def gap_through_stop_fixture() -> dict[str, Any]:
    rows = [
        _bar("2026-09-01T12:00:00Z", 1.10, 1.101, 1.099, 1.10, 0.0002),
        _bar("2026-09-01T12:05:00Z", 1.10, 1.101, 1.099, 1.10, 0.0002),
        _bar("2026-09-01T12:10:00Z", 1.07, 1.075, 1.06, 1.07, 0.0002),
    ]
    df = pd.DataFrame(rows)
    sl, tp = 1.09, 1.12
    _exit_i, exit_px, why = mark_exit(df, 2, "BUY", 1.10, sl, tp, 24)
    return {"why": why, "exit_px": exit_px, "expected_why": "stop_loss", "expected_px": sl, "note": "fill at stop not gap open"}


def slippage_fixture() -> dict[str, Any]:
    rows = [_bar("2026-09-01T12:00:00Z", 1.10, 1.101, 1.099, 1.10, 0.0002) for _ in range(3)]
    rows[1]["ask_open"] = 1.10010
    df = pd.DataFrame(rows)
    base = fill_price(df, 1, "BUY", "base")
    sev = fill_price(df, 1, "BUY", "severe")
    extra = 0.50 * 0.0004
    return {"base": base, "severe": sev, "expected_base": 1.10010, "expected_severe": 1.10010 + extra}


def convert_with_table(pnl_quote: float, pair: str, table: RateTable) -> ConversionResult:
    return convert_pnl(
        pnl_quote=pnl_quote,
        pair=pair,
        when=datetime(2026, 9, 1, 12, 5, tzinfo=timezone.utc),
        table=table,
    )


def missing_conversion_fixture() -> ConversionResult:
    return convert_pnl(
        pnl_quote=1.0,
        pair="EUR_USD",
        when=datetime(2026, 9, 1, 12, 5, tzinfo=timezone.utc),
        table=RateTable(),
    )


def drawdown_threshold() -> dict[str, Any]:
    start = 97.0
    path = [97.0, 100.0, 94.0]
    peak = start
    halt = None
    nav = start
    for nav in path:
        peak = max(peak, nav)
        dd = (peak - nav) / peak if peak else 0.0
        if dd >= 0.05:
            halt = "max_drawdown"
    return {"nav_path": path, "max_dd_frac": (peak - min(path)) / 100.0, "halt": halt, "expected_halt": "max_drawdown"}


def utc_day_rollover() -> dict[str, Any]:
    a = datetime(2026, 9, 1, 23, 55, tzinfo=timezone.utc).date().isoformat()
    b = datetime(2026, 9, 2, 0, 5, tzinfo=timezone.utc).date().isoformat()
    return {"day_a": a, "day_b": b, "expected_a": "2026-09-01", "expected_b": "2026-09-02"}

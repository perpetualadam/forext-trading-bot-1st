"""Quant V2 Experiment C primitives: M1 path-order of frozen M5 events. Research-only."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from forex_bot.decision_quality.cross_pair import reversal_instrument_side
from forex_bot.decision_quality.event_discovery import (
    POS_RANGE_Q1,
    POS_RANGE_Q5,
    enter_true_grouped,
    prior_rolling_extrema,
)
from forex_bot.decision_quality.feature_discovery import RANGE_SHORT, SYMBOLS
from forex_bot.decision_quality.spread_volume import apply_frozen_edges, half_close_spread
from forex_bot.profit_protection import pip_size
from forex_bot.session_rules import fx_market_open_at

# OANDA InstrumentsCandles `time` is the bar START. An M5 bar at t covers [t, t+5m)
# and is knowable only after t+5m. M1 bars t..t+4m formed that M5 bar and are excluded.
M5_MINUTES = 5
FIRST_ELIGIBLE_M1_OFFSET_MIN = M5_MINUTES

HURDLE_MULTS = (1.0, 1.5, 2.0, 3.0)
HORIZONS_MIN = (15, 30, 60, 120, 240, 480)

# Frozen Experiment B residual quintile edges (TRAIN). Do not refit.
RESID_PCA6_EDGES = (
    -0.007343785608701278,
    -0.00021615500470774783,
    -5.8241172034417324e-05,
    5.898286497246002e-05,
    0.0002158161844480932,
    0.009593179900670682,
)
PCA_WEIGHTS = {
    "EUR_USD": 0.3826791451527134,
    "GBP_USD": 0.42033418915928444,
    "USD_JPY": 0.420135385904811,
    "AUD_USD": 0.5047914399110883,
    "USD_CAD": 0.24366056395835575,
    "USD_CHF": 0.4314825958988349,
}
PCA_MEANS = {
    "EUR_USD": 1.2429041787559855e-06,
    "GBP_USD": 2.189809036763197e-06,
    "USD_JPY": 1.1433747155708329e-05,
    "AUD_USD": -1.1878573172995098e-05,
    "USD_CAD": -3.753022178956559e-07,
    "USD_CHF": -2.6613173592054044e-06,
}
PCA_BETAS = {
    "EUR_USD": 0.3826791451527139,
    "GBP_USD": 0.4203341891592841,
    "USD_JPY": 0.4201353859048107,
    "AUD_USD": 0.5047914399110884,
    "USD_CAD": 0.24366056395835584,
    "USD_CHF": 0.4314825958988346,
}

# Frozen V1 event families. Hypothesis is INSTRUMENT first-touch side.
EVENT_FAMILIES = {
    "range_bottom": {"hypothesis": "UP", "source": "V1 range_bottom_enter"},
    "range_top": {"hypothesis": "DOWN", "source": "V1 range_top_enter"},
    "breakout_up_24": {"hypothesis": "DOWN", "source": "V1 breakout_up_24 failure"},
    "breakout_dn_24": {"hypothesis": "UP", "source": "V1 breakout_dn_24 failure"},
    "resid_pos": {"hypothesis": "REVERSAL", "source": "B ENTER q5 resid_pca6"},
    "resid_neg": {"hypothesis": "REVERSAL", "source": "B ENTER q1 resid_pca6"},
}

LABELS = ("UP_FIRST", "DOWN_FIRST", "NEITHER", "M1_AMBIGUOUS", "INSUFFICIENT_DATA")


def first_eligible_m1_time(m5_event_time) -> pd.Timestamp:
    """First M1 bar start strictly after the completed M5 event is knowable."""
    t = pd.Timestamp(m5_event_time)
    return t + pd.Timedelta(minutes=FIRST_ELIGIBLE_M1_OFFSET_MIN)


def event_forming_m1_starts(m5_event_time) -> list[pd.Timestamp]:
    """The five M1 starts that constitute the M5 event bar. Not eligible as future path."""
    t = pd.Timestamp(m5_event_time)
    return [t + pd.Timedelta(minutes=i) for i in range(M5_MINUTES)]


def last_m1_time_for_horizon(first_eligible: pd.Timestamp, horizon_min: int) -> pd.Timestamp:
    return pd.Timestamp(first_eligible) + pd.Timedelta(minutes=int(horizon_min) - 1)


def instrument_reversal_side(symbol: str, residual_usd: float) -> str:
    """Map B residual reversal to instrument UP/DOWN. BUY=UP, SELL=DOWN."""
    side = reversal_instrument_side(symbol, residual_usd)
    if side == "BUY":
        return "UP"
    if side == "SELL":
        return "DOWN"
    return "NONE"


def half_spread_price(ask_close: float, bid_close: float) -> float:
    return float(half_close_spread(np.array([ask_close]), np.array([bid_close]))[0])


def half_spread_pips(ask_close: float, bid_close: float, symbol: str) -> float:
    pip = pip_size(symbol)
    return half_spread_price(ask_close, bid_close) / pip if pip else float("nan")


def classify_same_bar_touch(high: float, low: float, entry: float, thresh: float) -> str | None:
    """If both hurdles print inside one M1 bar, order is unknowable."""
    up = high >= entry + thresh
    dn = low <= entry - thresh
    if up and dn:
        return "M1_AMBIGUOUS"
    if up:
        return "UP_FIRST"
    if dn:
        return "DOWN_FIRST"
    return None


def first_touch_labels(
    m1_times: np.ndarray,
    m1_high: np.ndarray,
    m1_low: np.ndarray,
    *,
    first_eligible: pd.Timestamp,
    entry_close: float,
    cost_price: float,
    expected_open: set[pd.Timestamp] | None = None,
    expected_times: list | np.ndarray | None = None,
    m1_index: dict | None = None,
    max_horizon_min: int = 480,
) -> dict[str, dict[str, str | float | None]]:
    """
    For each hurdle and horizon, classify first-touch using only M1 after first_eligible.

    Missing expected market-open minutes before a unique order → INSUFFICIENT_DATA.
    Same-M1-candle both-touch → M1_AMBIGUOUS. Never invents intra-minute order.
    """
    times = pd.to_datetime(m1_times)
    highs = np.asarray(m1_high, dtype=float)
    lows = np.asarray(m1_low, dtype=float)
    first = pd.Timestamp(first_eligible)
    out: dict[str, dict[str, str | float | None]] = {}
    if not np.isfinite(entry_close) or not np.isfinite(cost_price) or cost_price <= 0:
        for hz in (h for h in HORIZONS_MIN if h <= int(max_horizon_min)):
            for m in HURDLE_MULTS:
                out[f"{hz}m_{m:g}x"] = {"label": "INSUFFICIENT_DATA", "bars_to_touch": None}
        return out

    by_time = m1_index if m1_index is not None else {pd.Timestamp(t): i for i, t in enumerate(times)}
    horizons = tuple(h for h in HORIZONS_MIN if h <= int(max_horizon_min))
    last480 = last_m1_time_for_horizon(first, int(max_horizon_min))
    if expected_times is not None:
        expected = [pd.Timestamp(t) for t in expected_times]
    elif expected_open is None:
        expected = []
        cur = first
        while cur <= last480:
            if fx_market_open_at(cur.to_pydatetime()):
                expected.append(cur)
            cur += pd.Timedelta(minutes=1)
    else:
        expected = sorted(t for t in expected_open if first <= t <= last480)

    # One walk: first unique order (or same-bar ambiguity) per multiplier.
    first_label = {m: "NEITHER" for m in HURDLE_MULTS}
    first_bars = {m: None for m in HURDLE_MULTS}
    first_when = {m: None for m in HURDLE_MULTS}
    insuff_from = None
    walked = 0
    for ts in expected:
        idx = by_time.get(pd.Timestamp(ts))
        if idx is None:
            insuff_from = pd.Timestamp(ts)
            break
        walked += 1
        h = float(highs[idx])
        lo = float(lows[idx])
        for mult in HURDLE_MULTS:
            if first_label[mult] != "NEITHER":
                continue
            hit = classify_same_bar_touch(h, lo, float(entry_close), float(mult) * float(cost_price))
            if hit is not None:
                first_label[mult] = hit
                first_bars[mult] = walked
                first_when[mult] = pd.Timestamp(ts)
        if all(first_label[m] != "NEITHER" for m in HURDLE_MULTS):
            break

    for hz in horizons:
        last = last_m1_time_for_horizon(first, hz)
        for mult in HURDLE_MULTS:
            when = first_when[mult]
            if when is not None and when <= last:
                lab, bars = first_label[mult], first_bars[mult]
            elif insuff_from is not None and insuff_from <= last:
                lab, bars = "INSUFFICIENT_DATA", None
            else:
                lab, bars = "NEITHER", None
            out[f"{hz}m_{mult:g}x"] = {"label": lab, "bars_to_touch": bars}
    return out


def summarize_labels(labels: list[str], hyp: str) -> dict:
    n = len(labels)
    counts = {k: int(sum(1 for x in labels if x == k)) for k in LABELS}
    resolved = counts["UP_FIRST"] + counts["DOWN_FIRST"]
    if hyp == "UP":
        fav, adv = counts["UP_FIRST"], counts["DOWN_FIRST"]
    elif hyp == "DOWN":
        fav, adv = counts["DOWN_FIRST"], counts["UP_FIRST"]
    else:
        fav, adv = 0, 0
    return {
        "n": n,
        "resolved_n": resolved,
        **counts,
        "favorable_first": fav,
        "adverse_first": adv,
        "fav_rate": fav / n if n else None,
        "adv_rate": adv / n if n else None,
        "fav_minus_adv": (fav - adv) / n if n else None,
        "fav_rate_resolved": fav / resolved if resolved else None,
    }


def range_events(pos_in_range: np.ndarray, group: np.ndarray) -> dict[str, np.ndarray]:
    bottom = np.asarray(pos_in_range, dtype=float) <= POS_RANGE_Q1
    top = np.asarray(pos_in_range, dtype=float) >= POS_RANGE_Q5
    return {
        "range_bottom": enter_true_grouped(bottom, group),
        "range_top": enter_true_grouped(top, group),
    }


def breakout24_events(high: np.ndarray, low: np.ndarray, close: np.ndarray, group: np.ndarray) -> dict[str, np.ndarray]:
    prior_high = np.empty(len(close))
    prior_low = np.empty(len(close))
    # compute per group
    g = np.asarray(group)
    prior_high[:] = np.nan
    prior_low[:] = np.nan
    for sym in pd.unique(g):
        idx = np.flatnonzero(g == sym)
        prior_high[idx] = prior_rolling_extrema(np.asarray(high)[idx], RANGE_SHORT, "max")
        prior_low[idx] = prior_rolling_extrema(np.asarray(low)[idx], RANGE_SHORT, "min")
    up = np.asarray(close, dtype=float) > prior_high
    dn = np.asarray(close, dtype=float) < prior_low
    return {
        "breakout_up_24": enter_true_grouped(up, g),
        "breakout_dn_24": enter_true_grouped(dn, g),
    }


def residual_events(resid_pca6: np.ndarray, group: np.ndarray) -> dict[str, np.ndarray]:
    q = apply_frozen_edges(resid_pca6, np.array(RESID_PCA6_EDGES))
    return {
        "resid_pos": enter_true_grouped(q == 5, group),
        "resid_neg": enter_true_grouped(q == 1, group),
    }


def apply_frozen_pca_factor(usd_ret6_row: np.ndarray) -> float:
    """usd_ret6_row ordered as SYMBOLS. TRAIN means/weights frozen."""
    x = np.asarray(usd_ret6_row, dtype=float)
    mu = np.array([PCA_MEANS[s] for s in SYMBOLS], dtype=float)
    w = np.array([PCA_WEIGHTS[s] for s in SYMBOLS], dtype=float)
    if not np.isfinite(x).all():
        return float("nan")
    return float((x - mu) @ w)


def residual_from_frozen(symbol: str, usd_ret6: float, factor: float) -> float:
    return float(usd_ret6) - float(PCA_BETAS[symbol]) * float(factor)


def build_open_minute_index(start: datetime, end: datetime) -> set[pd.Timestamp]:
    out: set[pd.Timestamp] = set()
    cur = pd.Timestamp(start)
    last = pd.Timestamp(end)
    while cur <= last:
        if fx_market_open_at(cur.to_pydatetime()):
            out.add(cur)
        cur += pd.Timedelta(minutes=1)
    return out

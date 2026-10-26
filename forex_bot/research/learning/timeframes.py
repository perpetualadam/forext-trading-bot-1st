"""Research-only higher-timeframe aggregation. It does not emit trading signals."""

from __future__ import annotations

import pandas as pd

from forex_bot.research.learning.protocol import BAR_SECONDS

RESEARCH_ONLY = True
PRODUCTION_AUTHORISED = False
H1_MINUTES = 60
H4_MINUTES = 240


def research_pip_size(symbol: str) -> float:
    """Local quote-currency rule. It is not a broker contract check."""
    quote = symbol.split("_", 1)[1]
    return 0.01 if quote == "JPY" else 0.0001


def aggregate_bid_ask(frame: pd.DataFrame, period_minutes: int) -> tuple[pd.DataFrame, dict]:
    """Build a higher-timeframe candle only when every constituent M5 bar exists.

    The candle is labelled by its UTC open. Its close becomes known at open plus
    the period. Missing bars are left missing.
    """
    if period_minutes % 5 != 0 or period_minutes < 5:
        raise ValueError("period_must_be_a_multiple_of_five_minutes")
    required = ("time", "bid_open", "bid_high", "bid_low", "bid_close", "ask_open", "ask_high", "ask_low", "ask_close")
    missing = [name for name in required if name not in frame.columns]
    if missing:
        raise ValueError("missing_columns:" + ",".join(missing))
    work = frame.copy()
    work["time"] = pd.to_datetime(work["time"], utc=True, errors="coerce")
    work = work.dropna(subset=["time"]).sort_values("time").drop_duplicates("time", keep="first")
    expected = period_minutes // 5
    period_ns = period_minutes * 60 * 1_000_000_000
    bucket_ns = (work["time"].astype("int64") // period_ns) * period_ns
    work["bucket"] = pd.to_datetime(bucket_ns, utc=True)
    step = pd.Timedelta(seconds=BAR_SECONDS)
    rows = []
    incomplete = 0
    for start, group in work.groupby("bucket", sort=True):
        group = group.sort_values("time")
        wanted = pd.date_range(start, periods=expected, freq=step)
        have = pd.DatetimeIndex(group["time"])
        flags_ok = True
        if "complete" in group.columns:
            flags_ok = not group["complete"].astype(str).str.lower().isin(["false", "0"]).any()
        if len(have) != expected or not have.equals(wanted) or not flags_ok:
            incomplete += 1
            continue
        rows.append(
            {
                "time": start,
                "available_at": start + pd.Timedelta(minutes=period_minutes),
                "bid_open": float(group["bid_open"].iloc[0]),
                "bid_high": float(group["bid_high"].max()),
                "bid_low": float(group["bid_low"].min()),
                "bid_close": float(group["bid_close"].iloc[-1]),
                "ask_open": float(group["ask_open"].iloc[0]),
                "ask_high": float(group["ask_high"].max()),
                "ask_low": float(group["ask_low"].min()),
                "ask_close": float(group["ask_close"].iloc[-1]),
                "volume": None if "volume" not in group.columns else float(pd.to_numeric(group["volume"], errors="coerce").sum()),
                "constituents": expected,
            }
        )
    candles = pd.DataFrame(rows)
    return candles, {
        "period_minutes": period_minutes,
        "expected_constituents": expected,
        "complete_candles": int(len(candles)),
        "incomplete_buckets": int(incomplete),
        "volume_rule": "sum_of_constituent_m5_volume",
        "missing_prices_forward_filled": False,
        "label": "utc_open",
        "known_at": "utc_open_plus_period",
    }


def visible_close(candles: pd.DataFrame, decision_time: pd.Timestamp) -> float | None:
    """Return the last higher-timeframe close that had already finished."""
    if candles.empty:
        return None
    known = candles.loc[candles["available_at"] <= decision_time]
    if known.empty:
        return None
    return float(known["bid_close"].iloc[-1])

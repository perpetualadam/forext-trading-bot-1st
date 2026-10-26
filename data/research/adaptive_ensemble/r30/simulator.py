"""Offline scalp lifecycle. Research only. Does not place orders or read secrets."""

from __future__ import annotations

import math
from datetime import datetime, time, timedelta, timezone
from typing import Any

import pandas as pd

from forex_bot.shadow.signals import build_feature_pack, signal_from_arrays

LOOKBACK = 50
BAR = timedelta(minutes=5)
STOP_DISTANCE = 0.002
TAKE_DISTANCE = 0.004
RISK_FRACTION = 0.01
START_CASH = 10000.0
SESSION_START = time(8, 0)
SESSION_END = time(22, 0)
WEEK_CLOSE = time(21, 0)
FLATTEN_START = time(20, 45)


def _utc(value: Any) -> datetime:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    else:
        stamp = stamp.tz_convert("UTC")
    return stamp.to_pydatetime()


def market_open(stamp: datetime) -> bool:
    moment = stamp.astimezone(timezone.utc)
    weekday = moment.weekday()
    clock = moment.time().replace(second=0, microsecond=0)
    if weekday == 5:
        return False
    if weekday == 6:
        return clock >= WEEK_CLOSE
    if weekday == 4:
        return clock < WEEK_CLOSE
    return True


def in_session(stamp: datetime) -> bool:
    if not market_open(stamp):
        return False
    clock = stamp.astimezone(timezone.utc).time().replace(second=0, microsecond=0)
    return SESSION_START <= clock <= SESSION_END


def in_flatten(stamp: datetime) -> bool:
    moment = stamp.astimezone(timezone.utc)
    if moment.weekday() != 4 or not market_open(stamp):
        return False
    clock = moment.time().replace(second=0, microsecond=0)
    return FLATTEN_START <= clock < WEEK_CLOSE


def entry_events(signals: list[str | None]) -> list[int]:
    """Indices where a directional state differs from the previous bar."""
    events = []
    previous = None
    for index, signal in enumerate(signals):
        if signal in {"BUY", "SELL"} and signal != previous:
            events.append(index)
        previous = signal
    return events


def scalp_signals(frame: pd.DataFrame) -> list[str | None]:
    work = pd.DataFrame(
        {
            "open": frame["bid_open"],
            "high": frame["bid_high"],
            "low": frame["bid_low"],
            "close": frame["bid_close"],
        }
    )
    pack = build_feature_pack(work, LOOKBACK, 250)
    output: list[str | None] = []
    for index in range(int(pack["n"])):
        direction, _reason = signal_from_arrays("scalp", index, pack)
        output.append(direction)
    return output


def _quote(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def prepare_bars(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Sort, parse UTC timestamps, and drop rows that cannot be filled."""
    work = frame.copy()
    exclusions = {"duplicate_timestamps": 0, "bad_timestamp": 0, "bad_quote": 0, "incomplete": 0}
    if "complete" in work.columns:
        incomplete = work["complete"].astype(str).str.lower().isin({"false", "0", "no"})
        exclusions["incomplete"] = int(incomplete.sum())
        work = work.loc[~incomplete]
    stamps = pd.to_datetime(work["time"], utc=True, errors="coerce")
    exclusions["bad_timestamp"] = int(stamps.isna().sum())
    work = work.loc[stamps.notna()].copy()
    work["_time"] = stamps.loc[stamps.notna()].to_numpy()
    work = work.sort_values("_time")
    duplicate = work["_time"].duplicated(keep="first")
    exclusions["duplicate_timestamps"] = int(duplicate.sum())
    work = work.loc[~duplicate]
    required = (
        "bid_open",
        "bid_high",
        "bid_low",
        "bid_close",
        "ask_open",
        "ask_high",
        "ask_low",
        "ask_close",
    )
    good = pd.Series(True, index=work.index)
    for column in required:
        parsed = work[column].map(_quote)
        good = good & parsed.notna()
        work[column] = parsed
    exclusions["bad_quote"] = int((~good).sum())
    work = work.loc[good].reset_index(drop=True)
    return work, exclusions


def _size(cash: float) -> float:
    if not math.isfinite(cash) or cash <= 0 or STOP_DISTANCE <= 0:
        return 0.0
    units = cash * RISK_FRACTION / STOP_DISTANCE
    if not math.isfinite(units) or units < 1:
        return 0.0
    return units


def _close_trade(
    trades: list[dict[str, Any]],
    position: dict[str, Any],
    *,
    exit_index: int,
    exit_time: datetime,
    exit_price: float,
    exit_mid: float,
    reason: str,
    slippage: float,
) -> None:
    direction = position["direction"]
    adverse = slippage if slippage > 0 else 0.0
    if direction == "BUY":
        filled = exit_price - adverse
        pnl = (filled - position["entry_price"]) * position["units"]
        gross = (exit_mid - position["entry_mid"]) * position["units"]
    else:
        filled = exit_price + adverse
        pnl = (position["entry_price"] - filled) * position["units"]
        gross = (position["entry_mid"] - exit_mid) * position["units"]
    trades.append(
        {
            "direction": direction,
            "signal_index": position["signal_index"],
            "entry_index": position["entry_index"],
            "exit_index": exit_index,
            "signal_time": position["signal_time"],
            "entry_time": position["entry_time"],
            "exit_time": exit_time,
            "entry_price": position["entry_price"],
            "exit_price": filled,
            "entry_mid": position["entry_mid"],
            "exit_mid": exit_mid,
            "stop": position["stop"],
            "take_profit": position["take_profit"],
            "units": position["units"],
            "pnl": pnl,
            "mid_pnl": gross,
            "exit_reason": reason,
            "holding_seconds": (exit_time - position["entry_time"]).total_seconds(),
        }
    )


def _bracket(position: dict[str, Any], row: pd.Series) -> tuple[float, float, str] | None:
    """Return exit price, midpoint reference, and reason. None if the bracket is untouched."""
    if position["direction"] == "BUY":
        open_ = float(row["bid_open"])
        high = float(row["bid_high"])
        low = float(row["bid_low"])
        mid_open = (float(row["bid_open"]) + float(row["ask_open"])) / 2
        stop = position["stop"]
        take = position["take_profit"]
        if open_ <= stop:
            return open_, mid_open, "stop_gap"
        if open_ >= take:
            return open_, mid_open, "take_profit_gap"
        hit_stop = low <= stop
        hit_take = high >= take
        if hit_stop and hit_take:
            return stop, stop, "ambiguous_stop"
        if hit_stop:
            return stop, stop, "stop"
        if hit_take:
            return take, take, "take_profit"
        return None
    open_ = float(row["ask_open"])
    high = float(row["ask_high"])
    low = float(row["ask_low"])
    mid_open = (float(row["bid_open"]) + float(row["ask_open"])) / 2
    stop = position["stop"]
    take = position["take_profit"]
    if open_ >= stop:
        return open_, mid_open, "stop_gap"
    if open_ <= take:
        return open_, mid_open, "take_profit_gap"
    hit_stop = high >= stop
    hit_take = low <= take
    if hit_stop and hit_take:
        return stop, stop, "ambiguous_stop"
    if hit_stop:
        return stop, stop, "stop"
    if hit_take:
        return take, take, "take_profit"
    return None


def simulate(
    frame: pd.DataFrame,
    signals: list[str | None],
    *,
    slippage: float = 0.0,
    starting_cash: float = START_CASH,
) -> dict[str, Any]:
    """Apply the frozen lifecycle. ``signals[i]`` must depend only on bars through i."""
    if len(frame) != len(signals):
        raise ValueError("signal length does not match bars")
    cash = float(starting_cash)
    trades: list[dict[str, Any]] = []
    position: dict[str, Any] | None = None
    pending_entry: dict[str, Any] | None = None
    pending_exit = False
    curve: list[dict[str, Any]] = []
    scheduled = 0
    cancelled = 0
    n = len(frame)
    for index in range(n):
        row = frame.iloc[index]
        stamp = _utc(row["_time"])
        previous = _utc(frame.iloc[index - 1]["_time"]) if index else None
        gap = previous is not None and stamp - previous != BAR
        if position is not None and (gap or in_flatten(stamp) or not market_open(stamp)):
            if gap:
                reason = "gap_exit"
            elif in_flatten(stamp):
                reason = "weekend_flatten"
            else:
                reason = "market_closed"
            exit_price = float(row["bid_open"] if position["direction"] == "BUY" else row["ask_open"])
            exit_mid = (float(row["bid_open"]) + float(row["ask_open"])) / 2
            _close_trade(
                trades,
                position,
                exit_index=index,
                exit_time=stamp,
                exit_price=exit_price,
                exit_mid=exit_mid,
                reason=reason,
                slippage=slippage,
            )
            cash += trades[-1]["pnl"]
            position = None
            pending_exit = False
            if pending_entry is not None:
                pending_entry = None
                cancelled += 1
        elif position is not None and pending_exit:
            breached = _bracket(position, row)
            if breached is not None and breached[2] in {"stop_gap", "take_profit_gap"}:
                price, mid, reason = breached
                _close_trade(
                    trades,
                    position,
                    exit_index=index,
                    exit_time=stamp,
                    exit_price=price,
                    exit_mid=mid,
                    reason=reason,
                    slippage=slippage,
                )
            else:
                exit_price = float(row["bid_open"] if position["direction"] == "BUY" else row["ask_open"])
                exit_mid = (float(row["bid_open"]) + float(row["ask_open"])) / 2
                _close_trade(
                    trades,
                    position,
                    exit_index=index,
                    exit_time=stamp,
                    exit_price=exit_price,
                    exit_mid=exit_mid,
                    reason="signal_reversal",
                    slippage=slippage,
                )
            cash += trades[-1]["pnl"]
            position = None
            pending_exit = False
        elif position is None and pending_entry is not None:
            eligible = (
                not gap
                and in_session(stamp)
                and not in_flatten(stamp)
                and market_open(stamp)
            )
            units = _size(cash)
            if not eligible or units <= 0:
                pending_entry = None
                cancelled += 1
            else:
                direction = pending_entry["direction"]
                adverse = slippage if slippage > 0 else 0.0
                if direction == "BUY":
                    raw = float(row["ask_open"])
                    filled = raw + adverse
                    stop = filled - STOP_DISTANCE
                    take = filled + TAKE_DISTANCE
                else:
                    raw = float(row["bid_open"])
                    filled = raw - adverse
                    stop = filled + STOP_DISTANCE
                    take = filled - TAKE_DISTANCE
                mid = (float(row["bid_open"]) + float(row["ask_open"])) / 2
                position = {
                    "direction": direction,
                    "signal_index": pending_entry["signal_index"],
                    "entry_index": index,
                    "signal_time": pending_entry["signal_time"],
                    "entry_time": stamp,
                    "entry_price": filled,
                    "entry_mid": mid,
                    "stop": stop,
                    "take_profit": take,
                    "units": units,
                }
                pending_entry = None
        if position is not None:
            bracket = _bracket(position, row)
            if bracket is not None:
                price, mid, reason = bracket
                _close_trade(
                    trades,
                    position,
                    exit_index=index,
                    exit_time=stamp,
                    exit_price=price,
                    exit_mid=mid,
                    reason=reason,
                    slippage=slippage,
                )
                cash += trades[-1]["pnl"]
                position = None
                pending_exit = False
        signal = signals[index]
        previous_signal = signals[index - 1] if index else None
        if position is not None and signal in {"BUY", "SELL"} and signal != position["direction"]:
            pending_exit = True
        if (
            position is None
            and pending_entry is None
            and signal in {"BUY", "SELL"}
            and signal != previous_signal
            and index + 1 < n
            and in_session(stamp)
            and not in_flatten(stamp)
        ):
            pending_entry = {"direction": signal, "signal_index": index, "signal_time": stamp}
            scheduled += 1
        marked = cash
        if position is not None:
            if position["direction"] == "BUY":
                marked += (float(row["bid_close"]) - position["entry_price"]) * position["units"]
            else:
                marked += (position["entry_price"] - float(row["ask_close"])) * position["units"]
        curve.append({"time": stamp, "equity": marked, "open": position is not None})
    if position is not None:
        row = frame.iloc[-1]
        stamp = _utc(row["_time"])
        exit_price = float(row["bid_close"] if position["direction"] == "BUY" else row["ask_close"])
        exit_mid = (float(row["bid_close"]) + float(row["ask_close"])) / 2
        _close_trade(
            trades,
            position,
            exit_index=n - 1,
            exit_time=stamp,
            exit_price=exit_price,
            exit_mid=exit_mid,
            reason="end_of_data",
            slippage=slippage,
        )
        cash += trades[-1]["pnl"]
        curve[-1]["equity"] = cash
        curve[-1]["open"] = False
    return {
        "trades": trades,
        "curve": curve,
        "ending_cash": cash,
        "scheduled_entries": scheduled,
        "cancelled_entries": cancelled,
        "signals": {
            "BUY": sum(item == "BUY" for item in signals),
            "SELL": sum(item == "SELL" for item in signals),
            "none": sum(item not in {"BUY", "SELL"} for item in signals),
        },
        "entry_events": len(entry_events(signals)),
    }


def split_index(count: int) -> int:
    """First out-of-sample index. In-sample is ``[0, split)``."""
    if count < 2:
        raise ValueError("need at least two bars to split")
    return int(count * 0.70)


def summarize(result: dict[str, Any], *, start: int, end: int) -> dict[str, Any]:
    chosen = [trade for trade in result["trades"] if start <= int(trade["entry_index"]) < end]
    pnls = [float(trade["pnl"]) for trade in chosen]
    wins = [value for value in pnls if value > 0]
    losses = [value for value in pnls if value < 0]
    consecutive = 0
    max_consecutive = 0
    for trade in chosen:
        consecutive = consecutive + 1 if trade["pnl"] < 0 else 0
        max_consecutive = max(max_consecutive, consecutive)
    slice_peak = None
    slice_drawdown = 0.0
    for point_index, point in enumerate(result["curve"]):
        if point_index < start or point_index >= end:
            continue
        marked = float(point["equity"])
        slice_peak = marked if slice_peak is None else max(slice_peak, marked)
        if slice_peak:
            slice_drawdown = max(slice_drawdown, (slice_peak - marked) / slice_peak)
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    holds = [float(trade["holding_seconds"]) for trade in chosen]
    open_bars = 0
    for point_index, point in enumerate(result["curve"]):
        if start <= point_index < end and point["open"]:
            open_bars += 1
    reasons: dict[str, int] = {}
    for trade in chosen:
        reasons[trade["exit_reason"]] = reasons.get(trade["exit_reason"], 0) + 1
    span = max(end - start, 1)
    return {
        "trades": len(chosen),
        "long": sum(trade["direction"] == "BUY" for trade in chosen),
        "short": sum(trade["direction"] == "SELL" for trade in chosen),
        "pnl": sum(pnls),
        "mid_pnl": sum(float(trade["mid_pnl"]) for trade in chosen),
        "win_rate": (len(wins) / len(pnls)) if pnls else None,
        "average_win": (sum(wins) / len(wins)) if wins else None,
        "average_loss": (sum(losses) / len(losses)) if losses else None,
        "profit_factor": (gross_profit / gross_loss) if gross_loss else None,
        "max_drawdown_fraction": slice_drawdown,
        "max_consecutive_losses": max_consecutive,
        "average_holding_seconds": (sum(holds) / len(holds)) if holds else None,
        "bars_with_position": open_bars,
        "bar_exposure": open_bars / span,
        "exit_reasons": reasons,
    }

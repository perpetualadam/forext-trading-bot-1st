"""Inventory local candles and replay the unchanged scalp rule. No network."""

from __future__ import annotations

import hashlib
import json
import socket
import subprocess
import sys
import types
from pathlib import Path

import pandas as pd


class _BlockedSocket(socket.socket):
    def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("R29_NETWORK_BLOCKED")


def _blocked_name(*_args, **_kwargs):  # noqa: ANN002, ANN003
    raise RuntimeError("R29_DNS_BLOCKED")


socket.socket = _BlockedSocket  # type: ignore[misc]
socket.getaddrinfo = _blocked_name  # type: ignore[assignment]
socket.gethostbyname = _blocked_name  # type: ignore[assignment]
socket.create_connection = _blocked_name  # type: ignore[assignment]
dotenv = types.ModuleType("dotenv")
dotenv.load_dotenv = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
sys.modules["dotenv"] = dotenv
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from forex_bot.shadow.signals import build_feature_pack, signal_from_arrays  # noqa: E402
from forex_bot.strategy_meta import strategies  # noqa: E402

OUT = ROOT / "data" / "research" / "adaptive_ensemble" / "r29"
LOOKBACK = 50


def _profile(path: Path) -> dict:
    frame = pd.read_csv(path)
    stamps = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    duplicate = int(stamps.duplicated().sum())
    missing_time = int(stamps.isna().sum())
    ordered = stamps.dropna().sort_values()
    gaps = ordered.diff().dt.total_seconds().dropna()
    step = 60 if "_M1" in path.name else 300
    gap_count = int((gaps > step).sum()) if not gaps.empty else 0
    nulls = {column: int(frame[column].isna().sum()) for column in frame.columns}
    bid = [column for column in frame.columns if column.startswith("bid")]
    ask = [column for column in frame.columns if column.startswith("ask")]
    return {
        "path": str(path.relative_to(ROOT)),
        "rows": int(len(frame)),
        "columns": list(frame.columns),
        "start": None if ordered.empty else ordered.iloc[0].isoformat(),
        "end": None if ordered.empty else ordered.iloc[-1].isoformat(),
        "timezone": "UTC",
        "duplicate_timestamps": duplicate,
        "missing_timestamps": missing_time,
        "gaps_longer_than_timeframe": gap_count,
        "nulls": nulls,
        "bid_columns": bid,
        "ask_columns": ask,
        "pricing": "bid_and_ask" if bid and ask else "midpoint_only",
        "label": "local_file",
    }


def _replay(path: Path) -> dict:
    frame = pd.read_csv(path)
    work = pd.DataFrame(
        {
            "open": frame["bid_open"],
            "high": frame["bid_high"],
            "low": frame["bid_low"],
            "close": frame["bid_close"],
        }
    )
    pack = build_feature_pack(work, LOOKBACK, 250)
    counts = {"BUY": 0, "SELL": 0, "NO_SIGNAL": 0, "INSUFFICIENT_DATA": 0}
    spreads = []
    for index in range(int(pack["n"])):
        direction, reason = signal_from_arrays("scalp", index, pack)
        counts[direction or reason] += 1
        if direction:
            spreads.append(float(frame["ask_close"].iloc[index]) - float(frame["bid_close"].iloc[index]))
    checks = {}
    for index in (200, 1000, 10000):
        prefix = work.iloc[: index + 1]
        partial = build_feature_pack(prefix, LOOKBACK, 250)
        checks[str(index)] = signal_from_arrays("scalp", index, pack) == signal_from_arrays(
            "scalp", index, partial
        )
    again = build_feature_pack(work, LOOKBACK, 250)
    repeat = signal_from_arrays("scalp", int(pack["n"]) - 1, pack) == signal_from_arrays(
        "scalp", int(again["n"]) - 1, again
    )
    ordered = sorted(spreads)
    median = ordered[len(ordered) // 2] if ordered else None
    return {
        "instrument": "EUR_USD",
        "timeframe": "M5",
        "lookback": LOOKBACK,
        "price_used_for_signal": "bid_ohlc",
        "bars": int(pack["n"]),
        "signals": counts,
        "signal_bars": counts["BUY"] + counts["SELL"],
        "future_bar_checks_match": checks,
        "repeat_last_bar_matches": repeat,
        "spread_samples": len(spreads),
        "median_signal_spread": median,
        "simulated_trades": 0,
        "pnl": None,
        "pnl_reason": "The scalp rule has no exit, hold, commission, or financing definition.",
    }


def main() -> None:
    historical = ROOT / "data" / "historical"
    files = sorted(historical.glob("*_M5.csv"))
    files.extend(sorted((historical / "m1").glob("*_M1.csv")))
    files.extend(sorted((ROOT / "data" / "research" / "adaptive_ensemble" / "g3" / "normalized").glob("*_M5.csv")))
    files.append(ROOT / "data" / "eurusd_m5_2024_sample.csv")
    inventory = [_profile(path) for path in files]
    replay = _replay(historical / "EUR_USD_M5.csv")
    current = (ROOT / "forex_bot" / "shadow" / "signals.py").read_bytes()
    previous = subprocess.check_output(["git", "show", "HEAD:forex_bot/shadow/signals.py"], cwd=ROOT)
    document = {
        "selected": "scalp",
        "activation": {name: item.active for name, item in strategies.items()},
        "datasets": inventory,
        "replay": replay,
        "signals_py_sha256_before": hashlib.sha256(previous).hexdigest(),
        "signals_py_sha256_after": hashlib.sha256(current).hexdigest(),
    }
    (OUT / "data_and_replay.json").write_text(json.dumps(document, indent=2), encoding="utf-8")
    if not all(replay["future_bar_checks_match"].values()) or not replay["repeat_last_bar_matches"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

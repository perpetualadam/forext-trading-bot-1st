"""Run the frozen scalp lifecycle on local EUR_USD M5 data. No network."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import socket
import sys
import types
from pathlib import Path

import pandas as pd


class _BlockedSocket(socket.socket):
    def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("R30_NETWORK_BLOCKED")


def _blocked_name(*_args, **_kwargs):  # noqa: ANN002, ANN003
    raise RuntimeError("R30_DNS_BLOCKED")


socket.socket = _BlockedSocket  # type: ignore[misc]
socket.getaddrinfo = _blocked_name  # type: ignore[assignment]
socket.gethostbyname = _blocked_name  # type: ignore[assignment]
socket.create_connection = _blocked_name  # type: ignore[assignment]
dotenv = types.ModuleType("dotenv")
dotenv.load_dotenv = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
sys.modules["dotenv"] = dotenv

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "research" / "adaptive_ensemble" / "r30"
DATA = ROOT / "data" / "historical" / "EUR_USD_M5.csv"
SPEC = OUT / "01_frozen_lifecycle_specification.md"

from forex_bot.shadow.signals import build_feature_pack, signal_from_arrays  # noqa: E402
from forex_bot.strategy_meta import strategies  # noqa: E402

_spec = importlib.util.spec_from_file_location("r30_simulator", OUT / "simulator.py")
sim = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(sim)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonable(trade: dict) -> dict:
    row = dict(trade)
    for key in ("signal_time", "entry_time", "exit_time"):
        row[key] = row[key].isoformat()
    return row


def main() -> None:
    frozen = json.loads((OUT / "spec_freeze.json").read_text(encoding="utf-8"))
    spec_hash = _sha256(SPEC)
    if spec_hash != frozen["sha256"] or frozen.get("performance_measured") is not False:
        raise SystemExit("lifecycle specification changed after the freeze")
    raw = pd.read_csv(DATA)
    stamps = pd.to_datetime(raw["time"], utc=True, errors="coerce")
    gaps = stamps.dropna().sort_values().diff().dt.total_seconds().dropna()
    frame, exclusions = sim.prepare_bars(raw)
    signals = sim.scalp_signals(frame)
    work = pd.DataFrame(
        {
            "open": frame["bid_open"],
            "high": frame["bid_high"],
            "low": frame["bid_low"],
            "close": frame["bid_close"],
        }
    )
    full = build_feature_pack(work, sim.LOOKBACK, 250)
    leakage = {}
    for index in (200, 1000, 10000):
        partial = build_feature_pack(work.iloc[: index + 1], sim.LOOKBACK, 250)
        leakage[str(index)] = signal_from_arrays("scalp", index, full) == signal_from_arrays(
            "scalp", index, partial
        )
    if not all(leakage.values()):
        raise SystemExit("future-bar signal check failed")
    boundary = sim.split_index(len(frame))
    scenarios = {}
    primary = None
    for name, slippage in (("spread_only", 0.0), ("slippage_half_pip", 0.00005), ("slippage_one_pip", 0.0001)):
        result = sim.simulate(frame, signals, slippage=slippage)
        repeat = sim.simulate(frame, signals, slippage=slippage)
        if result["trades"] != repeat["trades"]:
            raise SystemExit(f"{name} was not repeatable")
        payload = {
            "slippage_per_side": slippage,
            "in_sample": sim.summarize(result, start=0, end=boundary),
            "out_of_sample": sim.summarize(result, start=boundary, end=len(frame)),
            "trades": len(result["trades"]),
            "ending_cash": result["ending_cash"],
            "scheduled_entries": result["scheduled_entries"],
            "cancelled_entries": result["cancelled_entries"],
        }
        scenarios[name] = payload
        if primary is None:
            primary = result
    assert primary is not None
    crossing = [
        trade
        for trade in primary["trades"]
        if int(trade["entry_index"]) < boundary <= int(trade["exit_index"])
    ]
    audit = pd.DataFrame([_jsonable(trade) for trade in primary["trades"]])
    audit.to_csv(OUT / "trade_audit.csv", index=False)
    pd.DataFrame(
        {
            "time": [point["time"].isoformat() for point in primary["curve"]],
            "equity": [point["equity"] for point in primary["curve"]],
            "open": [point["open"] for point in primary["curve"]],
        }
    ).to_csv(OUT / "equity_curve.csv", index=False)
    document = {
        "dataset": {
            "path": "data/historical/EUR_USD_M5.csv",
            "sha256": _sha256(DATA),
            "raw_rows": int(len(raw)),
            "cleaned_rows": int(len(frame)),
            "start": sim._utc(frame.iloc[0]["_time"]).isoformat(),
            "end": sim._utc(frame.iloc[-1]["_time"]).isoformat(),
            "timezone": "UTC",
            "duplicate_timestamps": int(stamps.duplicated().sum()),
            "missing_timestamps": int(stamps.isna().sum()),
            "gaps_longer_than_five_minutes": int((gaps > 300).sum()),
            "exclusions": exclusions,
            "bid_ask": "bid and ask OHLC; signal uses bid; long entries use ask and long exits use bid",
            "pricing_note": "Unqualified OHLC is the midpoint on the inspected R.29 sample and is not used for fills.",
        },
        "split": {
            "rule": "first 70 percent of cleaned bars, by the frozen floor(0.70 * count)",
            "boundary_index": boundary,
            "boundary_time": sim._utc(frame.iloc[boundary]["_time"]).isoformat(),
            "in_sample_bars": boundary,
            "out_of_sample_bars": int(len(frame) - boundary),
            "in_sample_entries_closed_out_of_sample": len(crossing),
        },
        "signals": primary["signals"],
        "entry_events": primary["entry_events"],
        "leakage_checks": leakage,
        "scenarios": scenarios,
        "costs_not_estimated": ["commission", "financing", "swap"],
        "activation": {name: item.active for name, item in strategies.items()},
        "authorised_for_live": {name: item.authorised_for_live for name, item in strategies.items()},
        "spec_sha256": spec_hash,
        "simulator_sha256": _sha256(OUT / "simulator.py"),
        "signals_py_sha256": _sha256(ROOT / "forex_bot" / "shadow" / "signals.py"),
    }
    (OUT / "performance.json").write_text(json.dumps(document, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

"""Screen the five inactive signals on the frozen R.30 lifecycle. No network."""

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
        raise RuntimeError("R31_NETWORK_BLOCKED")


def _blocked_name(*_args, **_kwargs):  # noqa: ANN002, ANN003
    raise RuntimeError("R31_DNS_BLOCKED")


socket.socket = _BlockedSocket  # type: ignore[misc]
socket.getaddrinfo = _blocked_name  # type: ignore[assignment]
socket.gethostbyname = _blocked_name  # type: ignore[assignment]
socket.create_connection = _blocked_name  # type: ignore[assignment]
dotenv = types.ModuleType("dotenv")
dotenv.load_dotenv = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
sys.modules["dotenv"] = dotenv

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "research" / "adaptive_ensemble" / "r31"
R30 = ROOT / "data" / "research" / "adaptive_ensemble" / "r30"
DATA = ROOT / "data" / "historical" / "EUR_USD_M5.csv"

from forex_bot.shadow.signals import build_feature_pack, signal_from_arrays  # noqa: E402
from forex_bot.strategy_meta import strategies  # noqa: E402


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


sim = _load(R30 / "simulator.py", "r30_simulator_r31")
rank = _load(OUT / "ranking.py", "r31_ranking_run")

FAMILIES = (
    (50, ("scalp", "trend", "mean_reversion")),
    (100, ("swing_trend", "swing_mean_reversion", "swing_breakout")),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _signals(strategy: str, pack: dict) -> list[str | None]:
    output = []
    for index in range(int(pack["n"])):
        direction, _reason = signal_from_arrays(strategy, index, pack)
        output.append(direction)
    return output


def _audit(trades: list[dict]) -> pd.DataFrame:
    rows = []
    for trade in trades:
        row = dict(trade)
        for key in ("signal_time", "entry_time", "exit_time"):
            row[key] = row[key].isoformat()
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    frozen = json.loads((OUT / "spec_freeze.json").read_text(encoding="utf-8"))
    spec_hash = _sha256(OUT / "01_comparison_protocol.md")
    if spec_hash != frozen["sha256"] or frozen.get("performance_measured") is not False:
        raise SystemExit("comparison protocol changed after the freeze")
    published = json.loads((R30 / "performance.json").read_text(encoding="utf-8"))
    simulator_hash = _sha256(R30 / "simulator.py")
    if simulator_hash != published["simulator_sha256"]:
        raise SystemExit("R.30 simulator hash differs from the published baseline")
    raw = pd.read_csv(DATA)
    frame, exclusions = sim.prepare_bars(raw)
    stamps = pd.to_datetime(raw["time"], utc=True, errors="coerce")
    gaps = stamps.dropna().sort_values().diff().dt.total_seconds().dropna()
    work = pd.DataFrame(
        {"open": frame["bid_open"], "high": frame["bid_high"], "low": frame["bid_low"], "close": frame["bid_close"]}
    )
    boundary = sim.split_index(len(frame))
    leakage = {}
    packs = {lookback: build_feature_pack(work, lookback, 250) for lookback, _names in FAMILIES}
    for lookback, names in FAMILIES:
        partial = build_feature_pack(work.iloc[:5001], lookback, 250)
        for name in names:
            leakage[name] = signal_from_arrays(name, 5000, packs[lookback]) == signal_from_arrays(name, 5000, partial)
    if not all(leakage.values()):
        raise SystemExit("future-bar signal check failed")
    results = {}
    ranking_rows = []
    for lookback, names in FAMILIES:
        pack = packs[lookback]
        for name in names:
            signals = _signals(name, pack)
            scenarios = {}
            primary = None
            for label, slippage in (("spread_only", 0.0), ("slippage_half_pip", 0.00005), ("slippage_one_pip", 0.0001)):
                result = sim.simulate(frame, signals, slippage=slippage)
                if label == "spread_only":
                    repeat = sim.simulate(frame, signals, slippage=0.0)
                    if result["trades"] != repeat["trades"]:
                        raise SystemExit(f"{name} was not repeatable")
                    primary = result
                scenarios[label] = {
                    "in_sample": sim.summarize(result, start=0, end=boundary),
                    "out_of_sample": sim.summarize(result, start=boundary, end=len(frame)),
                    "ending_cash": result["ending_cash"],
                    "trades": len(result["trades"]),
                    "scheduled_entries": result["scheduled_entries"],
                    "cancelled_entries": result["cancelled_entries"],
                }
            assert primary is not None
            if name == "scalp":
                baseline = published["scenarios"]["spread_only"]
                if len(primary["trades"]) != baseline["trades"] or abs(primary["ending_cash"] - baseline["ending_cash"]) > 1e-6:
                    raise SystemExit("scalp rerun does not match the published R.30 baseline")
            _audit(primary["trades"]).to_csv(OUT / f"trades_{name}.csv", index=False)
            spread_in = scenarios["spread_only"]["in_sample"]
            spread_out = scenarios["spread_only"]["out_of_sample"]
            slipped_out = scenarios["slippage_half_pip"]["out_of_sample"]
            decision = rank.assess(spread_in, spread_out, slipped_out)
            ranking_rows.append(
                {
                    "strategy": name,
                    "merits_validation": decision["merits_validation"],
                    "rejections": decision["rejections"],
                    "out_of_sample_profit_factor": spread_out["profit_factor"],
                    "out_of_sample_drawdown": spread_out["max_drawdown_fraction"],
                }
            )
            results[name] = {
                "lookback": lookback,
                "signals": primary["signals"],
                "entry_events": primary["entry_events"],
                "scenarios": scenarios,
                "screening": decision,
            }
    other_hashes = {
        path.name: _sha256(path)
        for path in sorted((ROOT / "data" / "historical").glob("*_M5.csv"))
    }
    document = {
        "protocol_sha256": spec_hash,
        "simulator_sha256": simulator_hash,
        "simulator_modified": False,
        "scalp_baseline_matches_r30": True,
        "dataset": {
            "path": "data/historical/EUR_USD_M5.csv",
            "sha256": _sha256(DATA),
            "rows": int(len(frame)),
            "start": sim._utc(frame.iloc[0]["_time"]).isoformat(),
            "end": sim._utc(frame.iloc[-1]["_time"]).isoformat(),
            "timezone": "UTC",
            "duplicate_timestamps": int(stamps.duplicated().sum()),
            "missing_timestamps": int(stamps.isna().sum()),
            "gaps_longer_than_five_minutes": int((gaps > 300).sum()),
            "exclusions": exclusions,
            "bid_ask": True,
        },
        "unused_m5_sha256": other_hashes,
        "unused_reason": "Protocol fixes EUR_USD M5 before results. Other pairs, M1, and the later g3 extract are not compared.",
        "split": {
            "boundary_index": boundary,
            "boundary_time": sim._utc(frame.iloc[boundary]["_time"]).isoformat(),
        },
        "leakage_at_bar_5000": leakage,
        "strategies": results,
        "validation_order": rank.order_passes(ranking_rows),
        "activation": {name: item.active for name, item in strategies.items()},
        "authorised_for_live": {name: item.authorised_for_live for name, item in strategies.items()},
        "costs_not_estimated": ["commission", "financing", "swap"],
    }
    (OUT / "performance.json").write_text(json.dumps(document, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

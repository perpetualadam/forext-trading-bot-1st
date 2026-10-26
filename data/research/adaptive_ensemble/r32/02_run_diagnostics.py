"""Run the frozen R.32 diagnostics. No network, no orders, no parameter changes."""

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
        raise RuntimeError("R32_NETWORK_BLOCKED")


def _blocked_name(*_args, **_kwargs):  # noqa: ANN002, ANN003
    raise RuntimeError("R32_DNS_BLOCKED")


socket.socket = _BlockedSocket  # type: ignore[misc]
socket.getaddrinfo = _blocked_name  # type: ignore[assignment]
socket.gethostbyname = _blocked_name  # type: ignore[assignment]
socket.create_connection = _blocked_name  # type: ignore[assignment]
dotenv = types.ModuleType("dotenv")
dotenv.load_dotenv = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
sys.modules["dotenv"] = dotenv

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "research" / "adaptive_ensemble" / "r32"
R31 = ROOT / "data" / "research" / "adaptive_ensemble" / "r31"
R30 = ROOT / "data" / "research" / "adaptive_ensemble" / "r30"
DATA = ROOT / "data" / "historical" / "EUR_USD_M5.csv"

from forex_bot.shadow.signals import build_feature_pack, signal_from_arrays  # noqa: E402
from forex_bot.strategy_meta import strategies  # noqa: E402

EXPECTED = {
    "simulator": "fad94aed899f146dd780db29e602801100277f922b2793156edd4926ad14c6cc",
    "r31_protocol": "6ca23bac5be4e5705bc5b761b23ed16880fb1b554491a0e5774c629abfdadc88",
    "dataset": "3ae3c4d061792353b94b8d2be73684f950362f135d47926d1bc8c11a24791091",
    "signals": "4dc8ce797299e42c200f59e760099a3688ff93f35a1f8ccdfd135ae91b4a7051",
    "performance": "4ffe74a270f38cdce7de2f566056e6e285608c50e3eef5d004578a38ac196eb9",
    "trades_mean_reversion": "06d78203f68f55d8b40146e0c5ecb15ee3130eabb6d6ffabd908ff833fca363c",
    "trades_swing_mean_reversion": "c0c2d8e3a62f45e1e5cf8b957db021cb56070dd7546e47a3ec7775efa3c3ab09",
}
CANDIDATES = (
    ("mean_reversion", 50, "trades_mean_reversion.csv"),
    ("swing_mean_reversion", 100, "trades_swing_mean_reversion.csv"),
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


diag = _load(OUT / "diagnostics.py", "r32_diagnostics")
sim = _load(R30 / "simulator.py", "r30_simulator_r32")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _plain(value):
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    return value


def _write(name: str, payload: dict) -> None:
    (OUT / name).write_text(json.dumps(_plain(payload), indent=2), encoding="utf-8")


def _records(frame: pd.DataFrame) -> list[dict]:
    return frame.to_dict(orient="records")


def _reconcile(name: str, rows: list[dict], published: dict, boundary: int) -> dict:
    parts = [diag.attribute_trade(row) for row in rows]
    pnl_gaps = [abs(part["quoted"] - float(row["pnl"])) for part, row in zip(parts, rows)]
    mid_gaps = [abs(part["price_movement"] - float(row["mid_pnl"])) for part, row in zip(parts, rows)]
    residuals = [abs(part["residual"]) for part in parts]
    in_rows = [row for row in rows if int(row["entry_index"]) < boundary]
    out_rows = [row for row in rows if int(row["entry_index"]) >= boundary]
    scenario = published["strategies"][name]["scenarios"]["spread_only"]
    checks = {
        "rows": len(rows) == int(scenario["trades"]),
        "in_sample_rows": len(in_rows) == int(scenario["in_sample"]["trades"]),
        "out_of_sample_rows": len(out_rows) == int(scenario["out_of_sample"]["trades"]),
        "pnl": diag.totals_match(sum(float(row["pnl"]) for row in rows), scenario["in_sample"]["pnl"] + scenario["out_of_sample"]["pnl"]),
        "in_sample_pnl": diag.totals_match(sum(float(row["pnl"]) for row in in_rows), scenario["in_sample"]["pnl"]),
        "out_of_sample_pnl": diag.totals_match(sum(float(row["pnl"]) for row in out_rows), scenario["out_of_sample"]["pnl"]),
        "mid_pnl": diag.totals_match(
            sum(float(row["mid_pnl"]) for row in rows),
            scenario["in_sample"]["mid_pnl"] + scenario["out_of_sample"]["mid_pnl"],
        ),
        "in_sample_mid_pnl": diag.totals_match(sum(float(row["mid_pnl"]) for row in in_rows), scenario["in_sample"]["mid_pnl"]),
        "out_of_sample_mid_pnl": diag.totals_match(sum(float(row["mid_pnl"]) for row in out_rows), scenario["out_of_sample"]["mid_pnl"]),
        "ending_cash": diag.totals_match(10000.0 + sum(float(row["pnl"]) for row in rows), scenario["ending_cash"]),
        "trade_pnl": max(pnl_gaps) <= diag.TRADE_TOLERANCE,
        "trade_mid": max(mid_gaps) <= diag.TRADE_TOLERANCE,
        "residual": max(residuals) <= diag.TRADE_TOLERANCE,
    }
    price = sum(part["price_movement"] for part in parts)
    execution = sum(part["execution_difference"] for part in parts)
    return {
        "checks": checks,
        "accepted": all(checks.values()),
        "max_trade_pnl_gap": max(pnl_gaps),
        "max_trade_mid_gap": max(mid_gaps),
        "max_residual": max(residuals),
        "price_movement": price,
        "execution_difference": execution,
        "spread_component": sum(part["spread_component"] for part in parts),
        "quoted_pnl": price + execution,
        "order_exit_trades": sum(not part["exit_spread_observed"] for part in parts),
        "quote_exit_trades": sum(part["exit_spread_observed"] for part in parts),
        "parts": parts,
    }


def _signals(name: str, pack: dict) -> list[str | None]:
    output = []
    for index in range(int(pack["n"])):
        direction, _reason = signal_from_arrays(name, index, pack)
        output.append(direction)
    return output


def _horizon_report(events: list[int], signals: list[str | None], times: list, mid: list[float], horizon: int) -> dict:
    complete = lambda index, bars: diag.horizon_complete(times, index, bars)
    overlapping = [index for index in events if complete(index, horizon)]
    kept = diag.select_nonoverlapping(events, horizon, complete)
    uniform = sum(1 for index in kept if diag.window_is_uniform(times, index, horizon))

    def _values(indices: list[int]) -> list[float]:
        return [
            diag.direction_adjusted(str(signals[index]), mid[index], mid[index + horizon])
            for index in indices
        ]

    return {
        "horizon_bars": horizon,
        "entry_events": len(events),
        "missing_horizon": len(events) - len(overlapping),
        "overlapping": diag.summarize_returns(_values(overlapping)),
        "nonoverlapping": diag.summarize_returns(_values(kept)),
        "nonoverlapping_uniform_windows": uniform,
        "kept": kept,
    }


def _primary(name: str, events: list[int], signals: list[str | None], times: list, frame: pd.DataFrame) -> dict:
    mid = ((frame["bid_close"] + frame["ask_close"]) / 2).tolist()
    close_spread = (frame["ask_close"] - frame["bid_close"]).tolist()
    open_spread = (frame["ask_open"] - frame["bid_open"]).tolist()
    horizons = {str(horizon): _horizon_report(events, signals, times, mid, horizon) for horizon in diag.HORIZONS}
    primary = horizons[str(diag.PRIMARY_HORIZON)]
    kept = primary["kept"]
    raw = [mid[index + diag.PRIMARY_HORIZON] - mid[index] for index in kept]
    labels = [str(signals[index]) for index in kept]
    values = diag.adjusted_array(raw, labels)
    buy = [value for value, label in zip(values, labels) if label == "BUY"]
    sell = [value for value, label in zip(values, labels) if label == "SELL"]
    seeds = diag.SEEDS[name]
    shuffle = diag.shuffle_means(raw, labels, seeds["shuffle"])
    coin = diag.coin_means(raw, seeds["coin"])
    interval = diag.block_interval(values, seeds["bootstrap"])
    quarters = []
    for quarter, _start, _end in diag.WINDOWS:
        chosen = [value for value, index in zip(values, kept) if diag.quarter_name(times[index]) == quarter]
        summary = diag.summarize_returns(chosen)
        quarters.append({"name": quarter, "count": summary["count"], "mean": summary["mean"]})
    spread = float(pd.Series([close_spread[index] for index in kept]).median()) if kept else None
    next_open = []
    for index in kept:
        if diag.horizon_complete(times, index, 1):
            next_open.append(open_spread[index + 1])
    decision = diag.decide(
        primary["nonoverlapping"]["mean"],
        primary["overlapping"]["mean"],
        interval,
        diag.linear_percentile(shuffle, 95),
        diag.linear_percentile(coin, 95),
        float(spread),
        quarters,
    )
    effect = None
    if primary["nonoverlapping"]["std"]:
        effect = primary["nonoverlapping"]["mean"] / primary["nonoverlapping"]["std"]
    for item in horizons.values():
        item.pop("kept", None)
    return {
        "horizons": horizons,
        "buy": diag.summarize_returns(buy),
        "sell": diag.summarize_returns(sell),
        "median_signal_spread": spread,
        "median_next_open_spread": float(pd.Series(next_open).median()) if next_open else None,
        "always_buy_mean": float(pd.Series(raw).mean()) if raw else None,
        "always_sell_mean": float((-pd.Series(raw)).mean()) if raw else None,
        "shuffle": {
            "draws": int(shuffle.size),
            "mean": float(shuffle.mean()),
            "p50": diag.linear_percentile(shuffle, 50),
            "p95": diag.linear_percentile(shuffle, 95),
            "minimum": float(shuffle.min()),
            "maximum": float(shuffle.max()),
            "values": shuffle.tolist(),
        },
        "coin": {
            "draws": int(coin.size),
            "mean": float(coin.mean()),
            "p50": diag.linear_percentile(coin, 50),
            "p95": diag.linear_percentile(coin, 95),
            "minimum": float(coin.min()),
            "maximum": float(coin.max()),
            "values": coin.tolist(),
        },
        "interval": None if interval is None else {"low": interval[0], "high": interval[1]},
        "quarters": quarters,
        "effect_size": effect,
        "decision": decision,
    }


def _turnover(rows: list[dict], excursions: list[dict]) -> dict:
    entry_times = pd.to_datetime([row["entry_time"] for row in rows], utc=True)
    weeks = [f"{stamp.isocalendar().year}-W{stamp.isocalendar().week:02d}" for stamp in entry_times]
    months = [stamp.strftime("%Y-%m") for stamp in entry_times]
    holds = [float(row["holding_seconds"]) for row in rows]
    spreads = [float(item["entry_spread"]) for item in excursions]
    mfes = [item["mfe"] for item in excursions if item["mfe"] is not None]
    mid = [float(row["mid_pnl"]) for row in rows]
    quoted = [float(row["pnl"]) for row in rows]
    units = [float(row["units"]) for row in rows]
    mid_mean = float(pd.Series(mid).mean())
    median_mfe = float(pd.Series(mfes).median()) if mfes else None
    median_spread = float(pd.Series(spreads).median())
    return {
        "trades": len(rows),
        "trades_per_iso_week": {key: weeks.count(key) for key in sorted(set(weeks))},
        "trades_per_month": {key: months.count(key) for key in sorted(set(months))},
        "mean_holding_seconds": float(pd.Series(holds).mean()),
        "median_holding_seconds": float(pd.Series(holds).median()),
        "reversal_exits": sum(row["exit_reason"] == "signal_reversal" for row in rows),
        "reversal_fraction": sum(row["exit_reason"] == "signal_reversal" for row in rows) / len(rows),
        "exit_reasons": {reason: sum(row["exit_reason"] == reason for row in rows) for reason in sorted({row["exit_reason"] for row in rows})},
        "median_entry_spread": median_spread,
        "median_entry_spread_pips": median_spread / diag.PIP,
        "median_mfe": median_mfe,
        "spread_over_median_mfe": (median_spread / median_mfe) if median_mfe else None,
        "mean_mid_pnl": mid_mean,
        "mean_quoted_pnl": float(pd.Series(quoted).mean()),
        "break_even_extra_price": (mid_mean / float(pd.Series(units).mean())) if mid_mean > 0 else None,
        "unobserved_intervals": sum(bool(item["unobserved_interval"]) for item in excursions),
        "intrabar_unknown": sum(bool(item["intrabar_order_unknown"]) for item in excursions),
        "empty_paths": sum(bool(item["empty_path"]) for item in excursions),
    }


def main() -> None:
    frozen = json.loads((OUT / "spec_freeze.json").read_text(encoding="utf-8"))
    spec_hash = _sha256(OUT / "01_diagnostic_protocol.md")
    if spec_hash != frozen["sha256"] or frozen.get("diagnostics_measured") is not False:
        raise SystemExit("diagnostic protocol changed after the freeze")
    hashes = {
        "simulator": _sha256(R30 / "simulator.py"),
        "r31_protocol": _sha256(R31 / "01_comparison_protocol.md"),
        "dataset": _sha256(DATA),
        "signals": _sha256(ROOT / "forex_bot" / "shadow" / "signals.py"),
        "performance": _sha256(R31 / "performance.json"),
        "trades_mean_reversion": _sha256(R31 / "trades_mean_reversion.csv"),
        "trades_swing_mean_reversion": _sha256(R31 / "trades_swing_mean_reversion.csv"),
    }
    if hashes != EXPECTED:
        _write("input_hashes.json", {"expected": EXPECTED, "actual": hashes})
        raise SystemExit("input hash mismatch")
    flags = {
        name: {"active": item.active, "authorised_for_live": item.authorised_for_live}
        for name, item in strategies.items()
    }
    if any(item["active"] or item["authorised_for_live"] for item in flags.values()):
        raise SystemExit("a strategy flag is set")
    published = json.loads((R31 / "performance.json").read_text(encoding="utf-8"))
    raw = pd.read_csv(DATA)
    frame, exclusions = sim.prepare_bars(raw)
    boundary = sim.split_index(len(frame))
    times = [pd.Timestamp(value).to_pydatetime() for value in frame["_time"]]
    work = pd.DataFrame(
        {"open": frame["bid_open"], "high": frame["bid_high"], "low": frame["bid_low"], "close": frame["bid_close"]}
    )
    packs = {}
    results = {}
    for name, lookback, filename in CANDIDATES:
        rows = _records(pd.read_csv(R31 / filename))
        reconciliation = _reconcile(name, rows, published, boundary)
        parts = reconciliation.pop("parts")
        if not reconciliation["accepted"]:
            _write("reconciliation.json", {"strategy": name, **reconciliation, "flags": flags})
            raise SystemExit(f"{name} did not reconcile to R.31")
        if lookback not in packs:
            packs[lookback] = build_feature_pack(work, lookback, 250)
        signals = _signals(name, packs[lookback])
        events = sim.entry_events(signals)
        signal_counts = {
            "BUY": sum(item == "BUY" for item in signals),
            "SELL": sum(item == "SELL" for item in signals),
            "none": sum(item not in {"BUY", "SELL"} for item in signals),
        }
        published_signals = published["strategies"][name]["signals"]
        if signal_counts != published_signals or len(events) != int(published["strategies"][name]["entry_events"]):
            _write(
                "signal_discrepancy.json",
                {"strategy": name, "recomputed": signal_counts, "published": published_signals, "events": len(events)},
            )
            raise SystemExit(f"{name} signals do not match R.31")
        excursions = [diag.excursion(frame, row) for row in rows]
        audit = []
        for row, part, extreme in zip(rows, parts, excursions):
            audit.append(
                {
                    "direction": row["direction"],
                    "entry_index": int(row["entry_index"]),
                    "exit_index": int(row["exit_index"]),
                    "exit_reason": row["exit_reason"],
                    "holding_seconds": float(row["holding_seconds"]),
                    "units": float(row["units"]),
                    "pnl": float(row["pnl"]),
                    "mid_pnl": float(row["mid_pnl"]),
                    "price_movement": part["price_movement"],
                    "execution_difference": part["execution_difference"],
                    "spread_component": part["spread_component"],
                    "residual": part["residual"],
                    "exit_spread_observed": part["exit_spread_observed"],
                    **extreme,
                }
            )
        pd.DataFrame(audit).to_csv(OUT / f"trades_{name}.csv", index=False)
        scenario = published["strategies"][name]["scenarios"]
        spread_total = scenario["spread_only"]["in_sample"]["pnl"] + scenario["spread_only"]["out_of_sample"]["pnl"]
        slippage = {
            label: {
                "quoted_pnl": item["in_sample"]["pnl"] + item["out_of_sample"]["pnl"],
                "difference_from_spread_only": item["in_sample"]["pnl"] + item["out_of_sample"]["pnl"] - spread_total,
            }
            for label, item in scenario.items()
        }
        results[name] = {
            "lookback": lookback,
            "reconciliation": reconciliation,
            "slippage_scenarios": slippage,
            "signals": signal_counts,
            "entry_events": len(events),
            "predictive": _primary(name, events, signals, times, frame),
            "turnover": _turnover(rows, excursions),
        }
    _write(
        "diagnostics.json",
        {
            "protocol_sha256": spec_hash,
            "input_hashes": hashes,
            "rows": int(len(frame)),
            "boundary_index": boundary,
            "exclusions": exclusions,
            "activation": flags,
            "costs_not_estimated": ["commission", "financing", "swap"],
            "strategies": results,
        },
    )


if __name__ == "__main__":
    main()

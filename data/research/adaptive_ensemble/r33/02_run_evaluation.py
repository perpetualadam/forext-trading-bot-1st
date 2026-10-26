"""Score the quant stub under the frozen R.33 protocol. No network and no orders."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import socket
import sys
import types
from pathlib import Path

import pandas as pd


class _BlockedSocket(socket.socket):
    def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("R33_NETWORK_BLOCKED")


def _blocked_name(*_args, **_kwargs):  # noqa: ANN002, ANN003
    raise RuntimeError("R33_DNS_BLOCKED")


socket.socket = _BlockedSocket  # type: ignore[misc]
socket.getaddrinfo = _blocked_name  # type: ignore[assignment]
socket.gethostbyname = _blocked_name  # type: ignore[assignment]
socket.create_connection = _blocked_name  # type: ignore[assignment]
dotenv = types.ModuleType("dotenv")
dotenv.load_dotenv = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
sys.modules["dotenv"] = dotenv

os.environ["ENSEMBLE_MODE"] = "quant"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
for _name in (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "MISTRAL_API_KEY",
    "XAI_API_KEY",
    "GROK_API_KEY",
    "GROQ_API_KEY",
    "VENICE_API_KEY",
    "QROK_API_KEY",
    "STUB_SMA_EPSILON",
    "STUB_MOMENTUM_THRESHOLD",
    "STUB_CONFIDENCE_SCALE",
    "AI_DISABLE_STUB",
):
    os.environ.pop(_name, None)

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "research" / "adaptive_ensemble" / "r33"
R32 = ROOT / "data" / "research" / "adaptive_ensemble" / "r32"
R30 = ROOT / "data" / "research" / "adaptive_ensemble" / "r30"
DATA = ROOT / "data" / "historical" / "EUR_USD_M5.csv"

from forex_bot.ai_ensemble import _quant_stub_vote  # noqa: E402
from forex_bot.indicators import compute_indicators  # noqa: E402
from forex_bot.strategy_meta import strategies  # noqa: E402


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


diag = _load(R32 / "diagnostics.py", "r32_diagnostics_r33")
score = _load(OUT / "scoring.py", "r33_scoring")
sim = _load(R30 / "simulator.py", "r30_simulator_r33")

EXPECTED_DATA = "3ae3c4d061792353b94b8d2be73684f950362f135d47926d1bc8c11a24791091"
EXPECTED_SIM = "fad94aed899f146dd780db29e602801100277f922b2793156edd4926ad14c6cc"


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


def _votes(frame: pd.DataFrame) -> list[dict]:
    close = frame["close"]
    returns = close.pct_change()
    rows = []
    for index in range(len(frame)):
        ret = returns.iloc[index]
        atr = frame["atr"].iloc[index]
        payload = {
            "symbol": "EUR_USD",
            "timeframe": "M5",
            "price": float(close.iloc[index]),
            "ma_fast": float(frame["ma_fast"].iloc[index]),
            "ma_slow": float(frame["ma_slow"].iloc[index]),
            "returns": None if pd.isna(ret) else float(ret),
            "atr": None if pd.isna(atr) else float(atr),
        }
        vote = _quant_stub_vote(payload)
        rows.append(vote)
    return rows


def _trailing_volatility_removals(atr: pd.Series, actionable: list[int]) -> int:
    removed = 0
    for index in actionable:
        start = max(0, index - 199)
        window = atr.iloc[start : index + 1].dropna()
        latest = atr.iloc[index]
        if len(window) < 20 or pd.isna(latest):
            continue
        high = float(window.quantile(0.90))
        low = float(window.quantile(0.10))
        if float(latest) > high * 2 or float(latest) < low * 0.5:
            removed += 1
    return removed


def main() -> None:
    frozen = json.loads((OUT / "spec_freeze.json").read_text(encoding="utf-8"))
    spec_hash = _sha256(OUT / "01_evaluation_protocol.md")
    if spec_hash != frozen["sha256"] or frozen.get("performance_measured") is not False:
        raise SystemExit("evaluation protocol changed after the freeze")
    data_hash = _sha256(DATA)
    simulator_hash = _sha256(R30 / "simulator.py")
    if data_hash != EXPECTED_DATA or simulator_hash != EXPECTED_SIM:
        raise SystemExit("input hash mismatch")
    flags = {
        name: {"active": item.active, "authorised_for_live": item.authorised_for_live}
        for name, item in strategies.items()
    }
    if any(item["active"] or item["authorised_for_live"] for item in flags.values()):
        raise SystemExit("a strategy flag is set")
    raw = pd.read_csv(DATA)
    bars, exclusions = sim.prepare_bars(raw)
    work = pd.DataFrame(
        {"open": bars["bid_open"], "high": bars["bid_high"], "low": bars["bid_low"], "close": bars["bid_close"]}
    )
    computed = compute_indicators(work)
    prefix = compute_indicators(work.iloc[:5001])
    aligned = {
        column: float(computed[column].iloc[5000]) == float(prefix[column].iloc[-1])
        for column in ("ma_fast", "ma_slow", "atr")
    }
    if not all(aligned.values()):
        raise SystemExit("feature prefix check failed")
    sample = _votes(computed.iloc[:200])
    if sample != _votes(computed.iloc[:200]):
        raise SystemExit("stub vote was not repeatable")
    votes = _votes(computed)
    times = [pd.Timestamp(value).to_pydatetime() for value in bars["_time"]]
    mid = ((bars["bid_close"] + bars["ask_close"]) / 2).tolist()
    close_spread = (bars["ask_close"] - bars["bid_close"]).tolist()
    actionable = [
        index
        for index, vote in enumerate(votes)
        if vote.get("allow") and vote.get("direction") in {"BUY", "SELL"}
    ]
    directions = [str(votes[index]["direction"]) for index in actionable]

    def _report(horizon: int) -> dict:
        complete = lambda index, bars_ahead: diag.horizon_complete(times, index, bars_ahead)
        overlapping = [index for index in actionable if complete(index, horizon)]
        kept = diag.select_nonoverlapping(actionable, horizon, complete)

        def _values(indices: list[int]) -> list[float]:
            return [
                diag.direction_adjusted(str(votes[index]["direction"]), mid[index], mid[index + horizon])
                for index in indices
            ]

        return {
            "horizon_bars": horizon,
            "missing": len(actionable) - len(overlapping),
            "overlapping": diag.summarize_returns(_values(overlapping)),
            "nonoverlapping": diag.summarize_returns(_values(kept)),
            "uniform": sum(1 for index in kept if diag.window_is_uniform(times, index, horizon)),
            "kept": kept,
        }

    horizons = {str(horizon): _report(horizon) for horizon in diag.HORIZONS}
    primary = horizons[str(diag.PRIMARY_HORIZON)]
    kept = primary["kept"]
    raw_moves = [mid[index + diag.PRIMARY_HORIZON] - mid[index] for index in kept]
    labels = [str(votes[index]["direction"]) for index in kept]
    values = diag.adjusted_array(raw_moves, labels)
    buy = [value for value, label in zip(values, labels) if label == "BUY"]
    sell = [value for value, label in zip(values, labels) if label == "SELL"]
    shuffle = diag.shuffle_means(raw_moves, labels, 33001)
    coin = diag.coin_means(raw_moves, 33101)
    interval = diag.block_interval(values, 33201)
    quarters = []
    for quarter, _start, _end in diag.WINDOWS:
        chosen = [value for value, index in zip(values, kept) if diag.quarter_name(times[index]) == quarter]
        summary = diag.summarize_returns(chosen)
        quarters.append({"name": quarter, "count": summary["count"], "mean": summary["mean"]})
    spread = float(pd.Series([close_spread[index] for index in kept]).median()) if kept else None
    decision = score.decide_stub(
        primary["nonoverlapping"]["mean"],
        primary["overlapping"]["mean"],
        interval,
        diag.linear_percentile(shuffle, 95),
        diag.linear_percentile(coin, 95),
        float(spread),
        quarters,
    )
    for item in horizons.values():
        item.pop("kept", None)
    counts = {
        "bars": len(votes),
        "allow": sum(bool(vote.get("allow")) for vote in votes),
        "abstain": sum(not vote.get("allow") for vote in votes),
        "BUY": sum(vote.get("direction") == "BUY" and vote.get("allow") for vote in votes),
        "SELL": sum(vote.get("direction") == "SELL" and vote.get("allow") for vote in votes),
        "direction_without_allow": sum(
            (not vote.get("allow")) and vote.get("direction") in {"BUY", "SELL"} for vote in votes
        ),
    }
    document = {
        "protocol_sha256": spec_hash,
        "dataset_sha256": data_hash,
        "simulator_sha256": simulator_hash,
        "rows": int(len(bars)),
        "exclusions": exclusions,
        "period_status": "research_exposed_threshold_provenance_unknown",
        "independent_holdout": False,
        "feature_prefix_bar_5000": aligned,
        "indicator_windows": {"ma_fast": 5, "ma_slow": 20, "atr": 14},
        "activation": flags,
        "components": {
            "quant_stub": decision,
            "external_llm": {"classification": "NOT_EVALUABLE", "rule": "network_and_secrets"},
            "rl_policy": {"classification": "NOT_EVALUABLE", "rule": "no_loaded_policy"},
            "sequence_model": {"classification": "NOT_EVALUABLE", "rule": "unreachable_and_untrained"},
            "combined_live_path": {"classification": "NOT_EVALUABLE", "rule": "rl_not_reproducible"},
        },
        "counts": counts,
        "volatility_gate_would_remove": _trailing_volatility_removals(computed["atr"], actionable),
        "volatility_gate_used_in_score": False,
        "predictive": {
            "horizons": horizons,
            "buy": diag.summarize_returns(buy),
            "sell": diag.summarize_returns(sell),
            "median_signal_spread": spread,
            "always_buy_mean": float(pd.Series(raw_moves).mean()) if raw_moves else None,
            "always_sell_mean": float((-pd.Series(raw_moves)).mean()) if raw_moves else None,
            "interval": None if interval is None else {"low": interval[0], "high": interval[1]},
            "shuffle_p95": diag.linear_percentile(shuffle, 95),
            "coin_p95": diag.linear_percentile(coin, 95),
            "quarters": quarters,
            "effect_size": (
                primary["nonoverlapping"]["mean"] / primary["nonoverlapping"]["std"]
                if primary["nonoverlapping"]["std"]
                else None
            ),
        },
        "costs_not_estimated": ["commission", "financing", "swap", "slippage"],
        "rl_incremental_effect": "not_estimated",
    }
    _ = directions
    (OUT / "evaluation.json").write_text(json.dumps(_plain(document), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

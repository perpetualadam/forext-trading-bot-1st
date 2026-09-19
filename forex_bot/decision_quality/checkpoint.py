"""Atomic research-runner checkpoints. Offline only; no broker I/O."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from forex_bot.decision_quality.engine import BacktestResult
from forex_bot.decision_quality.outcomes import TradeRecord
from forex_bot.decision_quality.snapshot import DecisionSnapshot
from forex_bot.symbols import DEFAULT_FOREX_SYMBOLS

BASELINE_SYMBOLS: tuple[str, ...] = tuple(DEFAULT_FOREX_SYMBOLS)
CHECKPOINT_SCHEMA = 1
MODE_BASELINE = "baseline"
MODE_STOP_WIDTH = "stop_width"

RESEARCH_IDENTITY_ENV = (
    "HYBRID_ROUTE_LOOKBACK",
    "SCALP_LOOKBACK",
    "SWING_LOOKBACK",
    "DEFAULT_INDICATOR_LOOKBACK",
    "STUB_MOMENTUM_THRESHOLD",
    "USE_ATR_STOPS",
    "SL_ATR_MULT",
    "SL_FALLBACK_PIPS",
    "MIN_STOP_DISTANCE_PRICE",
    "FX_WEEK_CLOSE_UTC",
    "FX_WEEK_OPEN_UTC",
    "FX_SESSION_ALWAYS",
)

CODE_IDENTITY_FILES = (
    "forex_bot/decision_quality/engine.py",
    "forex_bot/decision_quality/signal.py",
    "forex_bot/decision_quality/fast_cache.py",
    "forex_bot/decision_quality/invariants.py",
    "forex_bot/decision_quality/research_features.py",
    "forex_bot/decision_quality/execution_sim.py",
    "forex_bot/decision_quality/outcomes.py",
    "forex_bot/indicators.py",
    "forex_bot/strategy_meta.py",
    "forex_bot/trading.py",
    "forex_bot/session_rules.py",
    "forex_bot/ai_ensemble.py",
)


class CheckpointIncompatibleError(RuntimeError):
    """Existing checkpoint does not match current methodology/data/config."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def code_identity(root: Path | None = None) -> dict[str, str]:
    base = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    files: dict[str, str] = {}
    blob = hashlib.sha256()
    for rel in CODE_IDENTITY_FILES:
        path = base / rel
        if path.is_file():
            digest = sha256_file(path)
            files[rel.replace("\\", "/")] = digest
            blob.update(digest.encode("ascii"))
        else:
            files[rel.replace("\\", "/")] = "missing"
            blob.update(b"missing")
    return {"combined": blob.hexdigest(), "files": files}


def env_identity() -> dict[str, str]:
    return {name: (os.getenv(name) or "").strip() for name in RESEARCH_IDENTITY_ENV}


def run_identity(
    *,
    warmup: int,
    seed: int,
    impl: str,
    apply_session_hours: bool,
    apply_fx_week: bool,
    sl_atr_mult: float | None,
    mode: str,
    root: Path | None = None,
) -> dict[str, Any]:
    return {
        "schema": CHECKPOINT_SCHEMA,
        "mode": mode,
        "warmup": int(warmup),
        "seed": int(seed),
        "impl": str(impl),
        "apply_session_hours": bool(apply_session_hours),
        "apply_fx_week": bool(apply_fx_week),
        "sl_atr_mult": sl_atr_mult,
        "env": env_identity(),
        "code": code_identity(root),
    }


def baseline_unit_id(symbol: str) -> str:
    return f"{symbol}|baseline"


def stop_width_unit_id(symbol: str, sl_atr_mult: float) -> str:
    return f"{symbol}|atr_{float(sl_atr_mult):.2f}"


def identity_conflicts(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    conflicts: list[str] = []
    keys = (
        "schema",
        "mode",
        "warmup",
        "seed",
        "impl",
        "apply_session_hours",
        "apply_fx_week",
        "sl_atr_mult",
    )
    for key in keys:
        if expected.get(key) != actual.get(key):
            conflicts.append(f"{key}: checkpoint={expected.get(key)!r} current={actual.get(key)!r}")
    if expected.get("env") != actual.get("env"):
        conflicts.append("research env identity differs")
    exp_code = (expected.get("code") or {}).get("combined")
    act_code = (actual.get("code") or {}).get("combined")
    if exp_code != act_code:
        conflicts.append("research/code identity differs")
    return conflicts


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def empty_checkpoint(identity: dict[str, Any], units: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": CHECKPOINT_SCHEMA,
        "created_at_utc": utc_now(),
        "updated_at_utc": utc_now(),
        "identity": identity,
        "units": {u["unit_id"]: u for u in units},
    }


def planned_baseline_units(symbols: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for symbol in symbols or BASELINE_SYMBOLS:
        out.append(
            {
                "unit_id": baseline_unit_id(symbol),
                "symbol": symbol,
                "mode": MODE_BASELINE,
                "sl_atr_mult": None,
                "status": "pending",
                "started_at_utc": None,
                "finished_at_utc": None,
                "elapsed_seconds": None,
                "input_csv": None,
                "input_sha256": None,
                "input_mtime_ns": None,
                "input_size": None,
                "result_path": None,
                "trade_count": None,
                "signal_count": None,
                "bars": None,
            }
        )
    return out


def planned_stop_width_units(
    symbols: tuple[str, ...] | None = None,
    multipliers: tuple[float, ...] = (1.0, 1.25, 1.5, 2.0),
) -> list[dict[str, Any]]:
    """Future experiment work units. Not executed by the baseline runner."""
    out: list[dict[str, Any]] = []
    for symbol in symbols or BASELINE_SYMBOLS:
        for mult in multipliers:
            out.append(
                {
                    "unit_id": stop_width_unit_id(symbol, mult),
                    "symbol": symbol,
                    "mode": MODE_STOP_WIDTH,
                    "sl_atr_mult": float(mult),
                    "status": "pending",
                    "started_at_utc": None,
                    "finished_at_utc": None,
                    "elapsed_seconds": None,
                    "input_csv": None,
                    "input_sha256": None,
                    "input_mtime_ns": None,
                    "input_size": None,
                    "result_path": None,
                    "trade_count": None,
                    "signal_count": None,
                    "bars": None,
                }
            )
    return out


def _parse_dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def snapshot_from_dict(data: dict[str, Any]) -> DecisionSnapshot:
    payload = dict(data)
    payload["timestamp"] = _parse_dt(payload.get("timestamp")) or datetime(1970, 1, 1)
    allowed = {f.name for f in fields(DecisionSnapshot)}
    return DecisionSnapshot(**{k: v for k, v in payload.items() if k in allowed})


def trade_from_dict(data: dict[str, Any]) -> TradeRecord:
    snap = snapshot_from_dict(data["snapshot"])
    return TradeRecord(
        snapshot=snap,
        entry_time=_parse_dt(data["entry_time"]) or snap.timestamp,
        exit_time=_parse_dt(data.get("exit_time")),
        exit_reason=str(data.get("exit_reason") or ""),
        exit_price=data.get("exit_price"),
        realised_pips=data.get("realised_pips"),
        realised_r=data.get("realised_r"),
        win=data.get("win"),
        mfe_pips=float(data.get("mfe_pips") or 0.0),
        mae_pips=float(data.get("mae_pips") or 0.0),
        mfe_r=data.get("mfe_r"),
        mae_r=data.get("mae_r"),
        mfe_atr=data.get("mfe_atr"),
        mae_atr=data.get("mae_atr"),
        time_to_mfe_min=data.get("time_to_mfe_min"),
        time_to_mae_min=data.get("time_to_mae_min"),
        time_in_trade_min=data.get("time_in_trade_min"),
        sl_distance_pips=float(data.get("sl_distance_pips") or 0.0),
        tp_distance_pips=float(data.get("tp_distance_pips") or 0.0),
        sl_over_atr=data.get("sl_over_atr"),
        tp_over_atr=data.get("tp_over_atr"),
        max_tp_progress=data.get("max_tp_progress"),
        ambiguous=bool(data.get("ambiguous")),
        post_stop=dict(data.get("post_stop") or {}),
        forward=dict(data.get("forward") or {}),
        filter_tags=list(data.get("filter_tags") or []),
    )


def trade_to_dict(trade: TradeRecord) -> dict[str, Any]:
    snap = trade.snapshot.to_dict()
    return {
        "snapshot": snap,
        "entry_time": trade.entry_time.isoformat(),
        "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
        "exit_reason": trade.exit_reason,
        "exit_price": trade.exit_price,
        "realised_pips": trade.realised_pips,
        "realised_r": trade.realised_r,
        "win": trade.win,
        "mfe_pips": trade.mfe_pips,
        "mae_pips": trade.mae_pips,
        "mfe_r": trade.mfe_r,
        "mae_r": trade.mae_r,
        "mfe_atr": trade.mfe_atr,
        "mae_atr": trade.mae_atr,
        "time_to_mfe_min": trade.time_to_mfe_min,
        "time_to_mae_min": trade.time_to_mae_min,
        "time_in_trade_min": trade.time_in_trade_min,
        "sl_distance_pips": trade.sl_distance_pips,
        "tp_distance_pips": trade.tp_distance_pips,
        "sl_over_atr": trade.sl_over_atr,
        "tp_over_atr": trade.tp_over_atr,
        "max_tp_progress": trade.max_tp_progress,
        "ambiguous": trade.ambiguous,
        "post_stop": trade.post_stop,
        "forward": trade.forward,
        "filter_tags": trade.filter_tags,
    }


def result_to_payload(result: BacktestResult) -> dict[str, Any]:
    return {
        "symbol": result.symbol,
        "bars": result.bars,
        "signals": result.signals,
        "coverage_note": result.coverage_note,
        "execution_note": result.execution_note,
        "snapshot_count": len(result.snapshots),
        "trades": [trade_to_dict(t) for t in result.trades],
    }


def result_from_payload(payload: dict[str, Any]) -> BacktestResult:
    trades = [trade_from_dict(row) for row in payload.get("trades") or []]
    return BacktestResult(
        symbol=str(payload["symbol"]),
        bars=int(payload.get("bars") or 0),
        signals=int(payload.get("signals") or 0),
        trades=trades,
        snapshots=[],
        coverage_note=str(payload.get("coverage_note") or ""),
        execution_note=str(payload.get("execution_note") or ""),
    )


def write_result_artifact(path: Path, result: BacktestResult) -> None:
    atomic_write_json(path, result_to_payload(result))


def load_result_artifact(path: Path) -> BacktestResult:
    return result_from_payload(load_json(path))


def file_identity(path: Path) -> dict[str, Any]:
    st = path.stat()
    return {
        "input_csv": str(path.resolve()),
        "input_sha256": sha256_file(path),
        "input_mtime_ns": int(st.st_mtime_ns),
        "input_size": int(st.st_size),
    }


def load_or_create_checkpoint(
    path: Path,
    *,
    identity: dict[str, Any],
    units: list[dict[str, Any]],
    force_rerun: bool = False,
) -> dict[str, Any]:
    path = Path(path)
    if force_rerun or not path.is_file():
        payload = empty_checkpoint(identity, units)
        atomic_write_json(path, payload)
        return payload
    existing = load_json(path)
    conflicts = identity_conflicts(existing.get("identity") or {}, identity)
    if conflicts:
        raise CheckpointIncompatibleError(
            "refusing to resume incompatible checkpoint at "
            f"{path}: " + "; ".join(conflicts)
        )
    known = {u["unit_id"] for u in units}
    extra = [uid for uid in existing.get("units", {}) if uid not in known]
    missing = [u["unit_id"] for u in units if u["unit_id"] not in existing.get("units", {})]
    if extra or missing:
        raise CheckpointIncompatibleError(
            f"checkpoint unit set differs (extra={extra} missing={missing})"
        )
    return existing


def save_checkpoint(path: Path, payload: dict[str, Any]) -> None:
    payload["updated_at_utc"] = utc_now()
    atomic_write_json(path, payload)

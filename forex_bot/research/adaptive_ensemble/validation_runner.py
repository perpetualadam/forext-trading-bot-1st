"""Offline validation runner. Defaults to refusal and does not score strategies."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from forex_bot.research.adaptive_ensemble.g4_integrity import ROOT
from forex_bot.research.adaptive_ensemble.g4_policy import RUNNER_ID
from forex_bot.research.adaptive_ensemble.g4_sessions import REQUIRED_SESSIONS
from forex_bot.research.adaptive_ensemble.protocol import integrity_hash
from forex_bot.research.adaptive_ensemble.simulator_v2 import entry_fill, mark_exit_v2
from forex_bot.research.adaptive_ensemble.state_v2 import SCHEMA

TOKEN = "FUTURE_INDEPENDENT_EVALUATION_AUTHORISED"
PROTECTED = (
    ROOT / "data" / "historical",
    ROOT / "data" / "research" / "adaptive_ensemble" / "g1",
    ROOT / "data" / "research" / "adaptive_ensemble" / "g2",
    ROOT / "data" / "research" / "adaptive_ensemble" / "g3",
    ROOT / "data" / "research" / "adaptive_ensemble" / "g4",
    ROOT / "data" / "research" / "adaptive_ensemble" / "protocol_v1.json",
    ROOT / "data" / "research" / "adaptive_ensemble" / "assessment.json",
    ROOT / "data" / "research" / "adaptive_ensemble" / "evaluation_results.json",
)


class EvaluationRefused(RuntimeError):
    """The runner will not start a performance evaluation."""


def _relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def assert_output_allowed(path: Path) -> None:
    resolved = path.resolve()
    for protected in PROTECTED:
        target = protected.resolve()
        if resolved == target or _relative_to(resolved, target):
            raise EvaluationRefused("protected artifact path")


def dry_run(
    *,
    authorised: bool = False,
    package: dict[str, Any],
    policy: dict[str, Any],
    complete_common_sessions: int,
    conversion_status: str,
    bid_ask_ok: bool,
    unresolved_gaps: int,
    warmup_ok: bool,
    model_schema: str,
    market_frames: Any = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    if market_frames is not None:
        raise EvaluationRefused("dry run cannot accept market frames")
    if output_dir is not None:
        assert_output_allowed(output_dir)
    reasons: list[str] = []
    if integrity_hash(package) != package.get("integrity_hash"):
        reasons.append("INVALID_MANIFEST")
    if integrity_hash(policy) != policy.get("integrity_hash"):
        reasons.append("INVALID_POLICY")
    if model_schema != SCHEMA:
        reasons.append("MODEL_STATE_INVALID")
    if complete_common_sessions < REQUIRED_SESSIONS:
        reasons.append("INSUFFICIENT_INDEPENDENT_DURATION")
    if conversion_status != "ok":
        reasons.append("MISSING_CONVERSION")
    if not bid_ask_ok:
        reasons.append("MISSING_BID_ASK")
    if unresolved_gaps:
        reasons.append("UNRESOLVED_GAPS")
    if not warmup_ok:
        reasons.append("INSUFFICIENT_WARMUP")
    if not authorised:
        reasons.append("AUTHORISATION_REQUIRED")
    return {
        "runner": RUNNER_ID,
        "dry_run": True,
        "authorised": bool(authorised),
        "reasons": reasons,
        "refused": bool(reasons),
        "evaluation_started": False,
        "strategy_evaluation_performed": False,
        "signals_evaluated": False,
        "trades": None,
        "net_pnl_gbp": None,
        "broker_calls": 0,
        "docker": False,
        "live_trading": False,
    }


def execute_market(*_args: Any, **_kwargs: Any) -> None:
    raise EvaluationRefused("market evaluation is outside stage G.4")


def _synthetic_frame() -> pd.DataFrame:
    rows = []
    for idx in range(3):
        px = 1.10 + idx * 0.01
        rows.append(
            {
                "bid_open": px,
                "bid_high": px + 0.02,
                "bid_low": px - 0.05,
                "bid_close": px,
                "ask_open": px + 0.01,
                "ask_high": px + 0.03,
                "ask_low": px - 0.04,
                "ask_close": px + 0.01,
                "feat_atr": 0.0,
            }
        )
    rows[1]["ask_open"] = float("nan")
    return pd.DataFrame(rows)


def exercise_synthetic(token: str) -> dict[str, Any]:
    if token != TOKEN:
        raise EvaluationRefused("authorisation required")
    frame = _synthetic_frame()
    _price, missing = entry_fill(frame, 1, "BUY", "base")
    _exit_i, _exit_px, reason = mark_exit_v2(frame, 2, "BUY", 1.20, 1.50, 2, "base")
    return {
        "synthetic_only": True,
        "market_data_used": False,
        "strategy_performance_evidence": False,
        "net_pnl_gbp": None,
        "missing_ask": missing,
        "gap_exit_reason": reason,
    }

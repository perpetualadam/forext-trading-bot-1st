"""Strategy-health state machine. Diagnostic only. Never grants live authorisation."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from forex_bot.decision_repair import HEALTH_SCHEMA_VERSION
from forex_bot.live_safety import KNOWN_STRATEGY_NAMES

INACTIVE = "INACTIVE"
ELIGIBLE_FOR_OFFLINE_REVIEW = "ELIGIBLE_FOR_OFFLINE_REVIEW"
SUSPENDED_RISK = "SUSPENDED_RISK"
SUSPENDED_PERFORMANCE = "SUSPENDED_PERFORMANCE"
OPERATOR_DISABLED = "OPERATOR_DISABLED"
STATES = (
    INACTIVE,
    ELIGIBLE_FOR_OFFLINE_REVIEW,
    SUSPENDED_RISK,
    SUSPENDED_PERFORMANCE,
    OPERATOR_DISABLED,
)
HISTORICALLY_DISQUALIFIED = frozenset(KNOWN_STRATEGY_NAMES)
MIN_SAMPLE = 30
DEFAULT_PATH = Path("data") / "research" / "decision_repair" / "strategy_health.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def health_path() -> Path:
    raw = (os.getenv("DECISION_REPAIR_HEALTH_PATH") or "").strip()
    return Path(raw) if raw else DEFAULT_PATH


def _blank_row(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "state": INACTIVE,
        "reason": "default_inactive",
        "sample_count": 0,
        "sharpe": None,
        "changed_at_utc": _utc_now(),
        "authorised_for_live": False,
        "may_trade": False,
        "historically_disqualified": name in HISTORICALLY_DISQUALIFIED,
    }


def blank_document() -> dict[str, Any]:
    return {
        "schema_version": HEALTH_SCHEMA_VERSION,
        "updated_utc": _utc_now(),
        "strategies": {name: _blank_row(name) for name in KNOWN_STRATEGY_NAMES},
        "transitions": [],
    }


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return blank_document()
    try:
        blob = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return blank_document()
    if not isinstance(blob, dict) or int(blob.get("schema_version") or 0) != HEALTH_SCHEMA_VERSION:
        return blank_document()
    return blob


def _save(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def evaluate_name(
    name: str,
    *,
    pnl: list[float],
    operator_disabled: bool,
    risk_suspended: bool,
) -> dict[str, Any]:
    """Classify one strategy. Never sets may_trade True for the original six."""
    n = len(pnl)
    sharpe: float | None
    if n <= 10:
        sharpe = None
        evidence = "INSUFFICIENT_EVIDENCE"
    else:
        import numpy as np

        arr = np.array(pnl, dtype=float)
        sharpe = float(arr.mean() / (arr.std() + 1e-6))
        evidence = "SAMPLED" if n >= MIN_SAMPLE else "INSUFFICIENT_EVIDENCE"
    if operator_disabled:
        state, reason = OPERATOR_DISABLED, "operator_or_durable_inactive"
    elif risk_suspended:
        state, reason = SUSPENDED_RISK, "account_or_risk_latch"
    elif evidence == "INSUFFICIENT_EVIDENCE":
        state, reason = INACTIVE, f"insufficient_sample_n={n}"
    elif sharpe is not None and sharpe < 0:
        state, reason = SUSPENDED_PERFORMANCE, f"negative_sharpe_n={n}"
    else:
        state, reason = ELIGIBLE_FOR_OFFLINE_REVIEW, f"non_negative_sharpe_n={n}_not_a_live_permit"
    if name in HISTORICALLY_DISQUALIFIED:
        may_trade = False
        if state == ELIGIBLE_FOR_OFFLINE_REVIEW:
            reason = "historically_disqualified_offline_review_only"
    else:
        may_trade = False
    return {
        "name": name,
        "state": state,
        "reason": reason,
        "sample_count": n,
        "sharpe": sharpe,
        "evidence": evidence,
        "changed_at_utc": _utc_now(),
        "authorised_for_live": False,
        "may_trade": may_trade,
        "historically_disqualified": name in HISTORICALLY_DISQUALIFIED,
    }


def record_evaluation(
    *,
    pnl_by_name: dict[str, list[float]],
    operator_disabled: dict[str, bool],
    risk_suspended: bool = False,
    path: Path | None = None,
) -> dict[str, Any]:
    dest = path or health_path()
    doc = _load(dest)
    transitions: list[dict[str, Any]] = list(doc.get("transitions") or [])
    rows = doc.setdefault("strategies", {})
    for name in KNOWN_STRATEGY_NAMES:
        prev = rows.get(name) if isinstance(rows.get(name), dict) else _blank_row(name)
        nxt = evaluate_name(
            name,
            pnl=list(pnl_by_name.get(name) or []),
            operator_disabled=bool(operator_disabled.get(name)),
            risk_suspended=risk_suspended,
        )
        if prev.get("state") != nxt["state"] or prev.get("reason") != nxt["reason"]:
            transitions.append(
                {
                    "name": name,
                    "from": prev.get("state"),
                    "to": nxt["state"],
                    "reason": nxt["reason"],
                    "at_utc": nxt["changed_at_utc"],
                }
            )
        rows[name] = nxt
    doc["transitions"] = transitions[-500:]
    doc["updated_utc"] = _utc_now()
    _save(dest, doc)
    return doc

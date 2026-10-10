"""Conservative deterministic strategy selection. Effectiveness: UNVALIDATED.

Does not rank on historical P&L or missing RL state. Does not activate strategies.
"""

from __future__ import annotations

import json
import math
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from forex_bot.decision_repair import (
    CURSOR_SCHEMA_VERSION,
    POLICY_EFFECTIVENESS,
    POLICY_VERSION,
)
from forex_bot.strategy_meta import (
    SCALP_STRATEGY_KEYS,
    SWING_STRATEGY_KEYS,
    _env_float,
    _env_int,
    hybrid_enabled,
    strategies,
)

ALL_NAMES: tuple[str, ...] = tuple(sorted(set(SCALP_STRATEGY_KEYS) | set(SWING_STRATEGY_KEYS)))
NOT_EVALUATED = "NOT_EVALUATED"
UNAVAILABLE = "UNAVAILABLE"
_LAST_RESULT: SelectionResult | None = None


def last_selection() -> SelectionResult | None:
    return _LAST_RESULT


@dataclass
class CandidateRecord:
    name: str
    family: str
    active: bool
    authorised_for_live: bool
    eligible: bool
    reject_reason: str | None


@dataclass
class SelectionResult:
    selected: str | None
    lookback: int
    horizon: str
    policy_version: str = POLICY_VERSION
    effectiveness: str = POLICY_EFFECTIVENESS
    reason: str = "selected"
    candidates: list[CandidateRecord] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    cursor_before: str | None = None
    cursor_after: str | None = None


DEFAULT_CURSOR_PATH = Path("data") / "research" / "decision_repair" / "selection_cursor.json"
_CURSOR_LOCK = threading.Lock()


def cursor_path() -> Path:
    raw = (os.getenv("DECISION_REPAIR_SELECT_CURSOR_PATH") or "").strip()
    return Path(raw) if raw else DEFAULT_CURSOR_PATH


def next_eligible(eligible: list[str], last: str | None) -> str:
    """Rotate through a sorted eligible list. Empty last starts at the first name."""
    ordered = list(eligible)
    if not ordered:
        raise ValueError("no eligible names")
    if last is None or last not in ordered:
        after = [name for name in ordered if last is not None and name > last]
        return after[0] if after else ordered[0]
    return ordered[(ordered.index(last) + 1) % len(ordered)]


def _blank_cursor() -> dict[str, Any]:
    return {"schema_version": CURSOR_SCHEMA_VERSION, "by_symbol": {}, "integrity": "ok"}


def load_cursor_document(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return _blank_cursor()
    try:
        blob = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(blob, dict) or int(blob.get("schema_version") or 0) != CURSOR_SCHEMA_VERSION:
        return None
    if not isinstance(blob.get("by_symbol"), dict):
        return None
    return blob


def save_cursor_document(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _family_from_atr(routing_df: pd.DataFrame) -> tuple[tuple[str, ...], int, str, dict[str, Any]]:
    scalp_lb = _env_int("SCALP_LOOKBACK", 50)
    swing_lb = _env_int("SWING_LOOKBACK", 100)
    default_lb = _env_int("DEFAULT_INDICATOR_LOOKBACK", 50)
    meta: dict[str, Any] = {"atr_last": None, "atr_median": None, "threshold": None}
    if routing_df is None or routing_df.empty or "atr" not in routing_df.columns:
        return ALL_NAMES, default_lb, "legacy", {**meta, "route": "missing_atr"}
    atr_series = routing_df["atr"].dropna()
    if len(atr_series) < 5:
        return SCALP_STRATEGY_KEYS, scalp_lb, "scalp", {**meta, "route": "atr_warmup"}
    last_atr = float(routing_df["atr"].iloc[-1])
    med_atr = float(atr_series.median())
    meta["atr_last"] = last_atr
    meta["atr_median"] = med_atr
    if med_atr <= 0 or math.isnan(last_atr):
        return SCALP_STRATEGY_KEYS, scalp_lb, "scalp", {**meta, "route": "atr_invalid"}
    threshold = _env_float("HYBRID_ATR_SCALP_THRESHOLD", 1.0)
    meta["threshold"] = threshold
    if last_atr >= med_atr * threshold:
        return SCALP_STRATEGY_KEYS, scalp_lb, "scalp", {**meta, "route": "high_atr"}
    return SWING_STRATEGY_KEYS, swing_lb, "swing", {**meta, "route": "low_atr"}


def select_deterministic(
    symbol: str,
    routing_df: pd.DataFrame,
    *,
    active_override: dict[str, bool] | None = None,
    persist: bool = False,
    store_path: Path | None = None,
) -> SelectionResult:
    """Evaluate all six names. Rotate over active eligible candidates. Does not activate them."""
    hybrid = hybrid_enabled(symbol)
    if hybrid:
        family, lookback, horizon, route = _family_from_atr(routing_df)
    else:
        lookback = _env_int("DEFAULT_INDICATOR_LOOKBACK", 50)
        family, horizon, route = ALL_NAMES, "legacy", {"route": "legacy_all"}
    family_set = set(family)
    records: list[CandidateRecord] = []
    selectable: list[str] = []
    for name in ALL_NAMES:
        strat = strategies.get(name)
        active = bool(active_override[name]) if active_override and name in active_override else bool(
            getattr(strat, "active", False)
        )
        authorised = bool(getattr(strat, "authorised_for_live", False)) if strat is not None else False
        in_family = name in family_set
        if not in_family:
            rec = CandidateRecord(name, "other", active, authorised, False, "wrong_family")
        elif not active:
            rec = CandidateRecord(name, horizon, active, authorised, False, "inactive")
        else:
            rec = CandidateRecord(name, horizon, active, authorised, True, None)
            selectable.append(name)
        records.append(rec)
    global _LAST_RESULT
    dest = store_path or cursor_path()
    cursor_before: str | None = None
    if persist:
        with _CURSOR_LOCK:
            stored = load_cursor_document(dest)
            if stored is None:
                _LAST_RESULT = SelectionResult(
                    selected=None,
                    lookback=lookback,
                    horizon=horizon,
                    reason="SELECTOR_STATE_INVALID",
                    candidates=records,
                    inputs={"symbol": symbol, "hybrid": hybrid, **route, "cursor": UNAVAILABLE},
                )
                return _LAST_RESULT
            raw_last = stored.get("by_symbol", {}).get(symbol)
            cursor_before = str(raw_last) if raw_last else None
    if not selectable:
        _LAST_RESULT = SelectionResult(
            selected=None,
            lookback=lookback,
            horizon=horizon,
            reason="NO_ACTIVE_ELIGIBLE",
            candidates=records,
            inputs={"symbol": symbol, "hybrid": hybrid, **route},
            cursor_before=cursor_before,
        )
        return _LAST_RESULT
    chosen = next_eligible(selectable, cursor_before)
    for rec in records:
        if rec.name != chosen and rec.reject_reason is None:
            rec.reject_reason = "rotation_not_selected"
    if persist:
        with _CURSOR_LOCK:
            stored = load_cursor_document(dest)
            if stored is None:
                _LAST_RESULT = SelectionResult(
                    selected=None,
                    lookback=lookback,
                    horizon=horizon,
                    reason="SELECTOR_STATE_INVALID",
                    candidates=records,
                    inputs={"symbol": symbol, "hybrid": hybrid, **route},
                    cursor_before=cursor_before,
                )
                return _LAST_RESULT
            by_symbol = dict(stored.get("by_symbol") or {})
            by_symbol[symbol] = chosen
            stored["by_symbol"] = by_symbol
            save_cursor_document(dest, stored)
    _LAST_RESULT = SelectionResult(
        selected=chosen,
        lookback=lookback,
        horizon=horizon,
        reason="rotate_active_eligible",
        candidates=records,
        inputs={"symbol": symbol, "hybrid": hybrid, **route, "cursor_before": cursor_before},
        cursor_before=cursor_before,
        cursor_after=chosen,
    )
    return _LAST_RESULT

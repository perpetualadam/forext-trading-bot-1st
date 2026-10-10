"""Fail-closed dynamic-weight state. Does not alter Stage G WeightState v1."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from forex_bot.research.adaptive_ensemble.candidates import (
    GENERATORS,
    NO_TRADE,
    all_signals,
)
from forex_bot.research.adaptive_ensemble.models import (
    Decision,
    WeightState,
    model_dynamic,
)
from forex_bot.research.adaptive_ensemble.protocol import integrity_hash

SCHEMA = "exp_weights_v2"
WEIGHT_MIN = 0.05
WEIGHT_MAX = 5.0
ETA = 0.15
CANDIDATES = tuple(GENERATORS.keys())
CHANGE_CLASS = "BEHAVIOURAL_REPAIR_REQUIRES_REBASELINE"
STATUS_OK = "ok"
UNAVAILABLE = "MODEL_STATE_UNAVAILABLE"
INVALID = "MODEL_STATE_INVALID"
INCOMPATIBLE = "MODEL_STATE_INCOMPATIBLE"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def candidate_set_hash() -> str:
    return integrity_hash({"candidates": list(CANDIDATES)})


@dataclass
class WeightStateV2:
    schema: str = SCHEMA
    run_id: str = ""
    status: str = STATUS_OK
    weights: dict[str, float] = field(default_factory=lambda: {k: 1.0 for k in CANDIDATES})
    pending: list[dict[str, Any]] = field(default_factory=list)
    updates: int = 0
    last_feedback_id: str | None = None
    last_processed_ready_i: int = -1
    seen_feedback_ids: list[str] = field(default_factory=list)
    state_utc: str = ""
    integrity: str = ""

    def dump(self) -> dict[str, Any]:
        body = {
            "schema": self.schema,
            "run_id": self.run_id,
            "weights": dict(self.weights),
            "pending": list(self.pending),
            "updates": self.updates,
            "last_feedback_id": self.last_feedback_id,
            "last_processed_ready_i": self.last_processed_ready_i,
            "seen_feedback_ids": list(self.seen_feedback_ids),
            "state_utc": self.state_utc,
            "candidate_set": list(CANDIDATES),
            "candidate_set_hash": candidate_set_hash(),
        }
        body["integrity_hash"] = integrity_hash(body)
        return body


def initialise_fresh(*, run_id: str) -> WeightStateV2:
    if not run_id.strip():
        st = WeightStateV2(status=INVALID, run_id=run_id)
        return st
    st = WeightStateV2(run_id=run_id.strip(), status=STATUS_OK, state_utc=_now())
    st.integrity = integrity_hash(st.dump())
    return st


def _validate_blob(blob: dict[str, Any]) -> tuple[str, WeightStateV2 | None]:
    if blob.get("schema") != SCHEMA:
        return INCOMPATIBLE, None
    if blob.get("integrity_hash") != integrity_hash(blob):
        return INVALID, None
    cset = blob.get("candidate_set")
    if list(cset or []) != list(CANDIDATES):
        return INCOMPATIBLE, None
    if blob.get("candidate_set_hash") != candidate_set_hash():
        return INCOMPATIBLE, None
    raw_w = blob.get("weights")
    if not isinstance(raw_w, dict):
        return INVALID, None
    weights: dict[str, float] = {}
    for cid in CANDIDATES:
        if cid not in raw_w:
            return INCOMPATIBLE, None
        try:
            w = float(raw_w[cid])
        except (TypeError, ValueError):
            return INVALID, None
        if not math.isfinite(w) or w < WEIGHT_MIN or w > WEIGHT_MAX:
            return INVALID, None
        weights[cid] = w
    extra = set(raw_w) - set(CANDIDATES)
    if extra:
        return INCOMPATIBLE, None
    run_id = str(blob.get("run_id") or "")
    if not run_id:
        return INVALID, None
    pending = blob.get("pending") or []
    if not isinstance(pending, list):
        return INVALID, None
    seen = blob.get("seen_feedback_ids") or []
    if not isinstance(seen, list):
        return INVALID, None
    st = WeightStateV2(
        run_id=run_id,
        status=STATUS_OK,
        weights=weights,
        pending=list(pending),
        updates=int(blob.get("updates") or 0),
        last_feedback_id=blob.get("last_feedback_id"),
        last_processed_ready_i=int(blob.get("last_processed_ready_i") or -1),
        seen_feedback_ids=[str(x) for x in seen],
        state_utc=str(blob.get("state_utc") or ""),
        integrity=str(blob.get("integrity_hash") or ""),
    )
    return STATUS_OK, st


def load_v2(path: Path, *, fresh_run: bool = False, run_id: str | None = None) -> WeightStateV2:
    if not path.is_file():
        if fresh_run:
            return initialise_fresh(run_id=run_id or "fresh")
        return WeightStateV2(status=UNAVAILABLE, run_id=run_id or "")
    try:
        raw = path.read_text(encoding="utf-8")
        blob = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return WeightStateV2(status=INVALID, run_id=run_id or "")
    if not isinstance(blob, dict):
        return WeightStateV2(status=INVALID, run_id=run_id or "")
    code, st = _validate_blob(blob)
    if st is None:
        return WeightStateV2(status=code, run_id=str(blob.get("run_id") or run_id or ""))
    return st


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def save_v2(state: WeightStateV2, path: Path) -> None:
    if state.status != STATUS_OK:
        raise RuntimeError("refuse to persist invalid weight state")
    state.state_utc = _now()
    payload = state.dump()
    state.integrity = str(payload["integrity_hash"])
    atomic_write(path, json.dumps(payload, indent=2, sort_keys=True))


def enqueue_outcome_v2(
    state: WeightStateV2,
    *,
    candidate_id: str,
    ready_i: int,
    pnl: float,
    feedback_id: str,
) -> WeightStateV2:
    if state.status != STATUS_OK:
        return state
    if feedback_id in state.seen_feedback_ids:
        return state
    if candidate_id not in CANDIDATES:
        state.status = INCOMPATIBLE
        return state
    state.pending.append(
        {
            "candidate_id": candidate_id,
            "ready_i": int(ready_i),
            "pnl": float(pnl),
            "feedback_id": feedback_id,
        }
    )
    state.seen_feedback_ids.append(feedback_id)
    state.last_feedback_id = feedback_id
    return state


def apply_delayed_outcomes_v2(state: WeightStateV2, now_i: int, eta: float = ETA) -> WeightStateV2:
    if state.status != STATUS_OK:
        return state
    remain: list[dict[str, Any]] = []
    due = []
    for item in state.pending:
        if int(item["ready_i"]) > now_i:
            remain.append(item)
        else:
            due.append(item)
    due.sort(key=lambda x: (int(x["ready_i"]), str(x.get("feedback_id") or "")))
    for item in due:
        cid = str(item["candidate_id"])
        if cid not in state.weights:
            state.status = INCOMPATIBLE
            state.pending = remain + due
            return state
        pnl = float(item["pnl"])
        cur = float(state.weights[cid])
        factor = 1.0 + eta if pnl > 0 else 1.0 - eta
        state.weights[cid] = max(WEIGHT_MIN, min(WEIGHT_MAX, cur * factor))
        state.updates += 1
        state.last_processed_ready_i = max(state.last_processed_ready_i, int(item["ready_i"]))
    state.pending = remain
    return state


def model_dynamic_v2(snap: dict[str, Any], state: WeightStateV2, *, cost: str = "base") -> Decision:
    sigs = all_signals(snap)
    dirs = {k: v.direction for k, v in sigs.items()}
    if state.status != STATUS_OK:
        return Decision(NO_TRADE, state.status, "dynamic_weights_v2", None, dirs, True)
    bridge = WeightState()
    bridge.weights = dict(state.weights)
    d = model_dynamic(snap, bridge, cost=cost)
    return Decision(d.direction, d.reason, "dynamic_weights_v2", d.chosen, d.signals, d.abstain)


def sha256_file(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

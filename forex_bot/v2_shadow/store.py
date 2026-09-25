"""Append-only research JSONL. Separate from production trade rows. No DB migration."""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from forex_bot.v2_shadow.contract import ShadowOutcome, V2ShadowDecision

logger = logging.getLogger(__name__)

_DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data" / "research" / "v2_shadow"
OBS_NAME = "observations.jsonl"
OUT_NAME = "outcomes.jsonl"
DEFAULT_ARCHIVE_BYTES = 50 * 1024 * 1024

# Keys that must never appear in research JSONL (defense in depth).
_SECRET_SUBSTR = (
    "api_key",
    "access_token",
    "bot_token",
    "password",
    "secret",
    "authorization",
    "oanda_token",
    "telegram_token",
    "webhook",
    "bearer",
)


def default_store_dir(root: Path | None = None) -> Path:
    if root is None:
        return _DEFAULT_DIR
    return Path(root) / "data" / "research" / "v2_shadow"


def observations_path(store_dir: Path | None = None) -> Path:
    return (store_dir or default_store_dir()) / OBS_NAME


def outcomes_path(store_dir: Path | None = None) -> Path:
    return (store_dir or default_store_dir()) / OUT_NAME


def archive_limit_bytes() -> int:
    raw = (os.getenv("V2_SHADOW_ARCHIVE_BYTES") or "").strip()
    if not raw:
        return DEFAULT_ARCHIVE_BYTES
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_ARCHIVE_BYTES


def _is_secret_key(key: Any) -> bool:
    name = str(key).lower()
    return any(part in name for part in _SECRET_SUBSTR)


def redact_secrets(obj: Any) -> Any:
    """Drop secret-shaped keys. Never write tokens/passwords to JSONL."""
    if isinstance(obj, dict):
        return {k: redact_secrets(v) for k, v in obj.items() if not _is_secret_key(k)}
    if isinstance(obj, list):
        return [redact_secrets(item) for item in obj]
    return obj


def maybe_archive_jsonl(path: Path, *, limit_bytes: int | None = None) -> Path | None:
    """
    If the active JSONL exceeds the bound, rename it to a timestamped archive.

    Never deletes. limit_bytes <= 0 disables rotation.
    """
    limit = archive_limit_bytes() if limit_bytes is None else limit_bytes
    if limit <= 0 or not path.exists() or path.stat().st_size < limit:
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = path.with_name(f"{path.stem}.{stamp}{path.suffix}")
    n = 1
    while dest.exists():
        dest = path.with_name(f"{path.stem}.{stamp}_{n}{path.suffix}")
        n += 1
    path.rename(dest)
    return dest


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    maybe_archive_jsonl(path)
    line = json.dumps(redact_secrets(payload), separators=(",", ":"), ensure_ascii=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def append_observation(decision: V2ShadowDecision, store_dir: Path | None = None) -> Path:
    path = observations_path(store_dir)
    _append_jsonl(path, decision.to_dict())
    return path


STATUS_WRITTEN = "WRITTEN"
STATUS_ALREADY_EXISTS = "ALREADY_EXISTS"
STATUS_CONFLICT = "CONFLICT"
STATUS_STORE_UNSAFE = "STORE_UNSAFE"

_outcome_locks: dict[str, threading.Lock] = {}
_outcome_locks_guard = threading.Lock()
_outcome_states: dict[str, "_OutcomeIndex"] = {}


@dataclass
class OutcomeWriteResult:
    status: str
    path: Path
    reason: str = ""
    keys: list[str] = field(default_factory=list)
    conflict_keys: list[str] = field(default_factory=list)
    historical_duplicates: int = 0
    historical_conflicts: int = 0


@dataclass
class _OutcomeIndex:
    safe: bool
    keys: dict[str, str]
    historical_duplicates: int = 0
    historical_conflicts: int = 0
    unsafe_reason: str = ""


def reset_outcome_index_cache() -> None:
    """Test helper. Does not delete files."""
    _outcome_states.clear()


def _outcome_lock(path: Path) -> threading.Lock:
    key = str(path.resolve()) if path.exists() or path.parent.exists() else str(path)
    try:
        key = str(path.resolve())
    except OSError:
        key = str(path)
    with _outcome_locks_guard:
        lock = _outcome_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _outcome_locks[key] = lock
        return lock


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _norm_horizon(raw: Any) -> str | None:
    try:
        minutes = int(raw)
    except (TypeError, ValueError):
        text = str(raw or "").strip()
        if not text.isdigit():
            return None
        minutes = int(text)
    if minutes <= 0:
        return None
    return str(minutes)


def logical_key(decision_id: str, direction: str, horizon: Any) -> str | None:
    hz = _norm_horizon(horizon)
    side = str(direction or "").strip().upper()
    did = str(decision_id or "").strip()
    if not did or side not in ("BUY", "SELL") or hz is None:
        return None
    return f"{did}|{side}|{hz}"


def logical_outcome_units(payload: dict[str, Any]) -> dict[str, str]:
    """Map logical (decision_id, direction, horizon) -> canonical side payload."""
    decision_id = str(payload.get("decision_id") or "").strip()
    horizons = payload.get("horizons")
    if not decision_id or not isinstance(horizons, dict):
        return {}
    units: dict[str, str] = {}
    for hz_raw, blob in horizons.items():
        if not isinstance(blob, dict):
            continue
        skip = blob.get("skip_opportunity") if isinstance(blob.get("skip_opportunity"), dict) else {}
        for direction, field in (("BUY", "buy"), ("SELL", "sell")):
            side = blob.get(field)
            if not isinstance(side, dict):
                continue
            key = logical_key(decision_id, direction, hz_raw)
            if key is None:
                continue
            skip_field = "buy_would_cover_cost" if direction == "BUY" else "sell_would_cover_cost"
            units[key] = _canonical(
                {
                    "decision_id": decision_id,
                    "direction": direction,
                    "horizon": _norm_horizon(hz_raw),
                    "side": side,
                    "skip_cover": skip.get(skip_field),
                }
            )
    return units


def _outcome_sibling_files(active: Path) -> list[Path]:
    parent = active.parent
    if not parent.is_dir():
        return []
    files = [p for p in parent.glob("outcomes*.jsonl") if p.is_file()]
    files.sort(key=lambda p: (p.name != active.name, p.name))
    return files


def _index_outcome_file(path: Path, state: _OutcomeIndex) -> None:
    text = path.read_text(encoding="utf-8")
    if not text:
        return
    lines = text.splitlines()
    if text[-1] not in ("\n", "\r"):
        # Last line may be truncated; still attempt parse, fail closed if invalid.
        pass
    for line in lines:
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            state.safe = False
            state.unsafe_reason = f"malformed JSONL in {path.name}"
            return
        if not isinstance(row, dict):
            state.safe = False
            state.unsafe_reason = f"non-object JSONL row in {path.name}"
            return
        try:
            units = logical_outcome_units(row)
        except (TypeError, ValueError):
            state.safe = False
            state.unsafe_reason = f"uncanonical payload in {path.name}"
            return
        for key, canon in units.items():
            if key not in state.keys:
                state.keys[key] = canon
                continue
            if state.keys[key] == canon:
                state.historical_duplicates += 1
            else:
                state.historical_conflicts += 1
                state.keys[key] = f"CONFLICTED:{state.keys[key]}"


def _ensure_outcome_state(path: Path) -> _OutcomeIndex:
    ident = str(path.resolve()) if path.parent.exists() else str(path)
    cached = _outcome_states.get(ident)
    if cached is not None:
        return cached
    state = _OutcomeIndex(safe=True, keys={})
    for sibling in _outcome_sibling_files(path):
        try:
            _index_outcome_file(sibling, state)
        except OSError as exc:
            state.safe = False
            state.unsafe_reason = f"cannot read {sibling.name}: {exc}"
            break
        if not state.safe:
            break
    if state.historical_duplicates or state.historical_conflicts:
        logger.warning(
            "[V2 SHADOW] outcome store historical_duplicates=%s historical_conflicts=%s path=%s",
            state.historical_duplicates,
            state.historical_conflicts,
            path,
        )
    _outcome_states[ident] = state
    return state


def inspect_outcome_store(store_dir: Path | None = None) -> _OutcomeIndex:
    """Read-only index status. Does not write."""
    path = outcomes_path(store_dir)
    with _outcome_lock(path):
        return _ensure_outcome_state(path)


def append_outcome(outcome: ShadowOutcome, store_dir: Path | None = None) -> OutcomeWriteResult:
    """
    Persist a research outcome if its logical keys are new.

    Logical key: (decision_id, direction, horizon_minutes) extracted from the
    nested ShadowOutcome (one JSONL row may contain many keys). Never writes a
    second row for an existing key. Conflicts fail closed (no append).
    """
    path = outcomes_path(store_dir)
    payload = redact_secrets(outcome.to_dict() if hasattr(outcome, "to_dict") else dict(outcome))
    units = logical_outcome_units(payload)
    lock = _outcome_lock(path)
    with lock:
        state = _ensure_outcome_state(path)
        result = OutcomeWriteResult(status=STATUS_STORE_UNSAFE, path=path, keys=sorted(units))
        if not state.safe:
            result.reason = state.unsafe_reason or "outcome store cannot be indexed safely"
            logger.error("[V2 SHADOW] outcome persist fail-closed: %s", result.reason)
            return result
        result.historical_duplicates = state.historical_duplicates
        result.historical_conflicts = state.historical_conflicts
        if not units:
            result.status = STATUS_CONFLICT
            result.reason = "outcome has no logical (decision_id, direction, horizon) keys"
            logger.error("[V2 SHADOW] outcome persist rejected: %s", result.reason)
            return result

        overlap = [k for k in units if k in state.keys]
        new_keys = [k for k in units if k not in state.keys]
        conflicts = [k for k in overlap if state.keys[k] != units[k]]
        if conflicts:
            result.status = STATUS_CONFLICT
            result.reason = "conflicting payload for existing logical key"
            result.conflict_keys = conflicts
            logger.error(
                "[V2 SHADOW] outcome conflict decision keys=%s",
                ",".join(conflicts[:8]),
            )
            return result
        if overlap and new_keys:
            result.status = STATUS_CONFLICT
            result.reason = "partial overlap would duplicate existing logical keys"
            result.conflict_keys = overlap
            logger.error("[V2 SHADOW] outcome persist rejected: %s", result.reason)
            return result
        if overlap and not new_keys:
            result.status = STATUS_ALREADY_EXISTS
            result.reason = "identical logical outcome already stored"
            return result

        _append_jsonl(path, payload)
        state.keys.update(units)
        result.status = STATUS_WRITTEN
        result.reason = "written"
        return result

"""Versioned RL Q-table persistence. Offline/research by default. Fail closed."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from forex_bot.decision_repair import RL_SCHEMA_VERSION

MODEL_ID = "tabular_q_v1"
FEATURE_SPACE = "trend4_vol6"
ACTION_SPACE: tuple[str, ...] = ("BUY", "SELL", "SKIP")
UNAVAILABLE = "UNAVAILABLE"
PRODUCTION_RL_PATH = Path("data") / "ops" / "rl_q_table.json"
DEFAULT_RESEARCH_PATH = Path("data") / "research" / "decision_repair" / "rl_state.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def research_path() -> Path:
    raw = (os.getenv("DECISION_REPAIR_RL_PATH") or "").strip()
    return Path(raw) if raw else DEFAULT_RESEARCH_PATH


def production_path() -> Path:
    raw = (os.getenv("DECISION_REPAIR_RL_PRODUCTION_PATH") or "").strip()
    return Path(raw) if raw else PRODUCTION_RL_PATH


def config_fingerprint(alpha: float, epsilon: float) -> str:
    raw = f"alpha={alpha:.8f}|epsilon={epsilon:.8f}|actions={','.join(ACTION_SPACE)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _canonical_q(q: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for state in sorted(q):
        row = q[state]
        out[state] = {a: float(row.get(a, 0.0)) for a in ACTION_SPACE}
    return out


def integrity_hash(payload: dict[str, Any]) -> str:
    clone = {k: v for k, v in payload.items() if k != "integrity"}
    text = json.dumps(clone, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_document(
    *,
    q: dict[str, dict[str, float]],
    alpha: float,
    epsilon: float,
    mode: str,
    model_id: str = MODEL_ID,
    strategy_id: str = "shared",
    created_utc: str | None = None,
) -> dict[str, Any]:
    now = _utc_now()
    doc: dict[str, Any] = {
        "schema_version": RL_SCHEMA_VERSION,
        "model_id": model_id,
        "strategy_id": strategy_id,
        "created_utc": created_utc or now,
        "updated_utc": now,
        "feature_space": FEATURE_SPACE,
        "action_space": list(ACTION_SPACE),
        "config_fingerprint": config_fingerprint(alpha, epsilon),
        "mode": mode,
        "q": _canonical_q(q),
    }
    doc["integrity"] = integrity_hash(doc)
    return doc


def validate_document(blob: Any, *, expected_fingerprint: str | None = None) -> dict[str, Any] | None:
    if not isinstance(blob, dict):
        return None
    try:
        ver = int(blob.get("schema_version") or 0)
    except (TypeError, ValueError):
        return None
    if ver != RL_SCHEMA_VERSION:
        return None
    if str(blob.get("model_id") or "") != MODEL_ID:
        return None
    if str(blob.get("feature_space") or "") != FEATURE_SPACE:
        return None
    actions = tuple(blob.get("action_space") or ())
    if actions != ACTION_SPACE:
        return None
    q = blob.get("q")
    if not isinstance(q, dict):
        return None
    expected = str(blob.get("integrity") or "")
    if not expected or integrity_hash(blob) != expected:
        return None
    if expected_fingerprint and str(blob.get("config_fingerprint") or "") != expected_fingerprint:
        return None
    return blob


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


class RLStore:
    """Load/save Q-tables. Experiments cannot overwrite the production path."""

    def __init__(self, path: Path, *, experiment: bool = False) -> None:
        self.path = path
        self.experiment = experiment
        self.loaded: dict[str, Any] | None = None
        self.status = UNAVAILABLE
        self.detail = "not_loaded"

    def _guard_write(self) -> None:
        prod = production_path().resolve()
        target = self.path.resolve()
        if self.experiment and target == prod:
            raise PermissionError("offline experiment cannot write production RL state")
        if self.experiment and "data/ops" in str(target).replace("\\", "/"):
            raise PermissionError("offline experiment cannot write data/ops")

    def save(
        self,
        q: dict[str, dict[str, float]],
        *,
        alpha: float,
        epsilon: float,
        mode: str,
        created_utc: str | None = None,
    ) -> dict[str, Any]:
        self._guard_write()
        doc = build_document(
            q=q, alpha=alpha, epsilon=epsilon, mode=mode, created_utc=created_utc
        )
        atomic_write(self.path, doc)
        self.loaded = doc
        self.status = "ok"
        self.detail = "saved"
        return doc

    def load(self, *, expected_fingerprint: str | None = None) -> dict[str, Any] | None:
        self.loaded = None
        self.status = UNAVAILABLE
        if not self.path.is_file():
            self.detail = "missing"
            return None
        try:
            blob = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            self.detail = "corrupt"
            return None
        valid = validate_document(blob, expected_fingerprint=expected_fingerprint)
        if valid is None:
            self.detail = "incompatible_or_corrupt"
            return None
        self.loaded = valid
        self.status = "ok"
        self.detail = "loaded"
        return valid

    def q_table(self) -> dict[str, dict[str, float]] | None:
        if self.status != "ok" or not self.loaded:
            return None
        raw = self.loaded.get("q") or {}
        if not isinstance(raw, dict):
            return None
        return _canonical_q({str(k): dict(v) for k, v in raw.items() if isinstance(v, dict)})

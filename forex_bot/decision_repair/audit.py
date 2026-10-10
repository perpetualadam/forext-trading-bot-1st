"""Append-only decision audit records. Never proof of a broker fill. No credentials."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from forex_bot.decision_repair import AUDIT_SCHEMA_VERSION
from forex_bot.decision_repair.flags import audit_enabled

NOT_EVALUATED = "NOT_EVALUATED"
UNAVAILABLE = "UNAVAILABLE"
DEFAULT_PATH = Path("data") / "research" / "decision_repair" / "decisions.jsonl"
MAX_BYTES = 8_000_000
FORBIDDEN_KEYS = frozenset(
    {
        "token",
        "api_key",
        "apikey",
        "authorization",
        "password",
        "secret",
        "oanda_token",
        "account_id",
        "oanda_account",
        "bearer",
    }
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def audit_path() -> Path:
    raw = (os.getenv("DECISION_REPAIR_AUDIT_PATH") or "").strip()
    return Path(raw) if raw else DEFAULT_PATH


def candle_fingerprint(row: dict[str, Any] | None) -> str:
    if not row:
        return UNAVAILABLE
    parts = [str(row.get(k, "")) for k in ("time", "open", "high", "low", "close")]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def new_decision_id() -> str:
    return uuid.uuid4().hex


def _redact(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in payload.items():
        lk = str(key).lower()
        if lk in FORBIDDEN_KEYS or any(part in lk for part in ("token", "secret", "password", "api_key")):
            continue
        out[key] = value
    return out


def empty_record(*, symbol: str) -> dict[str, Any]:
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "decision_id": new_decision_id(),
        "ts_utc": _utc_now(),
        "symbol": symbol,
        "candle_time": NOT_EVALUATED,
        "candle_fingerprint": NOT_EVALUATED,
        "feature_version": "indicators_v1",
        "indicators": NOT_EVALUATED,
        "candidates": NOT_EVALUATED,
        "candidate_eligibility": NOT_EVALUATED,
        "selected_strategy": NOT_EVALUATED,
        "selection_policy_version": NOT_EVALUATED,
        "ai_model_id": NOT_EVALUATED,
        "ai_vote": NOT_EVALUATED,
        "ai_confidence": NOT_EVALUATED,
        "rl_model_id": NOT_EVALUATED,
        "rl_state_fingerprint": NOT_EVALUATED,
        "rl_action": NOT_EVALUATED,
        "quant_filter": NOT_EVALUATED,
        "session_filter": NOT_EVALUATED,
        "risk_filter": NOT_EVALUATED,
        "position_sizing": NOT_EVALUATED,
        "final_decision": NOT_EVALUATED,
        "rejection_reasons": [],
        "live_order_auth_state": NOT_EVALUATED,
        "strategy_activation_state": NOT_EVALUATED,
        "client_order_id": NOT_EVALUATED,
        "order_intent_id": NOT_EVALUATED,
        "broker_request_id": NOT_EVALUATED,
        "order_submitted": False,
        "broker_ack": False,
        "submission_status": NOT_EVALUATED,
        "explicit_rejection_reason": NOT_EVALUATED,
        "path": NOT_EVALUATED,
        "stage": NOT_EVALUATED,
        "audit_delivery": "at_least_once_best_effort",
        "close_outcome": NOT_EVALUATED,
        "close_trigger": NOT_EVALUATED,
        "close_evidence": NOT_EVALUATED,
        "simulated": True,
        "not_broker_proof": True,
    }


def _rotate_if_needed(path: Path) -> None:
    if not path.is_file():
        return
    try:
        if path.stat().st_size < MAX_BYTES:
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path.rename(path.with_name(f"{path.stem}.{stamp}{path.suffix}"))
    except OSError:
        return


def append_record(record: dict[str, Any], path: Path | None = None) -> None:
    dest = path or audit_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    _rotate_if_needed(dest)
    clean = _redact(record)
    line = json.dumps(clean, sort_keys=True, default=str)
    with dest.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def append_record_safe(record: dict[str, Any], path: Path | None = None) -> bool:
    """Logging failure must not raise into the order path."""
    try:
        append_record(record, path)
        return True
    except (OSError, TypeError, ValueError):
        return False


_CURRENT: ContextVar[EvaluationAudit | None] = ContextVar("decision_eval_audit", default=None)
MAX_RECORD_CHARS = 16_000


class EvaluationAudit:
    """One evaluation attempt. Default-off. New-exposure writes fail closed when enabled."""

    def __init__(self, symbol: str, *, enabled: bool) -> None:
        self.enabled = enabled
        self.record = empty_record(symbol=symbol)
        self.emitted = False
        self._token: Token[EvaluationAudit | None] | None = None

    @classmethod
    def start(cls, symbol: str) -> EvaluationAudit:
        inst = cls(symbol, enabled=audit_enabled())
        inst._token = _CURRENT.set(inst)
        return inst

    def update(self, **fields: Any) -> None:
        if not self.enabled:
            return
        for key, value in fields.items():
            if key == "rejection_reasons" and isinstance(value, list):
                existing = self.record.get("rejection_reasons")
                if not isinstance(existing, list):
                    existing = []
                for item in value:
                    if item not in existing:
                        existing.append(item)
                self.record["rejection_reasons"] = existing
            else:
                self.record[key] = value

    def note_skip(self, *, reason: str, stage: str, **fields: Any) -> None:
        if not self.enabled:
            return
        reasons = list(self.record.get("rejection_reasons") or [])
        if reason not in reasons:
            reasons.append(reason)
        self.record["rejection_reasons"] = reasons
        self.record["explicit_rejection_reason"] = reason
        self.record["stage"] = stage
        self.record["final_decision"] = "reject"
        _apply_stage(self.record, stage, reason)
        for key, value in fields.items():
            if key in self.record:
                self.record[key] = value

    def note_close(
        self,
        *,
        outcome: str,
        trigger: str,
        evidence: str = NOT_EVALUATED,
    ) -> None:
        """Best-effort close audit. Never fail-closed. CLOSE_EXECUTED requires evidence."""
        if not self.enabled:
            return
        executed = outcome == "CLOSE_EXECUTED" and evidence in {
            "local_fill",
            "broker_fill",
            "reconciled",
            "mock_fill",
        }
        if outcome == "CLOSE_EXECUTED" and not executed:
            outcome = "CLOSE_STATUS_UNKNOWN"
            evidence = evidence if evidence != NOT_EVALUATED else "insufficient_execution_evidence"
        self.update(
            path="protective_close",
            final_decision=outcome,
            close_outcome=outcome,
            close_trigger=trigger,
            close_evidence=evidence,
            stage="position",
            audit_delivery="best_effort_close",
        )

    def note_error(self, reason: str) -> None:
        self.update(
            path="error",
            final_decision="error",
            explicit_rejection_reason=reason,
            rejection_reasons=[reason],
        )

    def permit_new_exposure(self) -> bool:
        """Write an order-intent record. If audit is on and write fails, block the open."""
        if not self.enabled:
            return True
        self.update(
            path="new_entry",
            final_decision="order_intent",
            submission_status="attempted",
            audit_delivery="fail_closed_new_exposure",
        )
        ok = self._write()
        return ok

    def finish(self) -> None:
        try:
            if self.enabled:
                if self.record.get("final_decision") == NOT_EVALUATED:
                    self.record["final_decision"] = "completed_no_new_exposure"
                self._write()
        finally:
            if self._token is not None:
                _CURRENT.reset(self._token)
                self._token = None

    def _write(self) -> bool:
        raw = json.dumps(self.record, sort_keys=True, default=str)
        if len(raw) > MAX_RECORD_CHARS:
            self.record["indicators"] = "truncated"
        ok = append_record_safe(self.record)
        self.emitted = self.emitted or ok
        return ok


def current_audit() -> EvaluationAudit | None:
    return _CURRENT.get()


def note_current_skip(*, symbol: str, reason: str, stage: str, **fields: Any) -> None:
    _ = symbol
    cur = _CURRENT.get()
    if cur is None:
        return
    cur.note_skip(reason=reason, stage=stage, **fields)


def reject_current(reason: str, *, stage: str, **fields: Any) -> None:
    cur = _CURRENT.get()
    if cur is None:
        return
    cur.note_skip(reason=reason, stage=stage, **fields)


def _apply_stage(record: dict[str, Any], stage: str, reason: str) -> None:
    if stage in ("session",):
        record["session_filter"] = reason
    elif stage in ("quant", "quant_ai"):
        record["quant_filter"] = reason
    elif stage in ("pretrade", "risk", "rl"):
        if stage == "rl":
            record["rl_action"] = reason
        else:
            record["risk_filter"] = reason
    elif stage in ("sizing", "entry_geometry"):
        record["position_sizing"] = reason
    if reason == "LIVE_ORDER_AUTH_BLOCKED" or reason.startswith("live_order_auth"):
        record["live_order_auth_state"] = "BLOCKED"

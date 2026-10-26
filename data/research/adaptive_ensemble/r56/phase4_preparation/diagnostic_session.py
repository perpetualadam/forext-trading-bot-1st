"""Offline diagnostic session. Phase 2 adapters and the Phase 3 gate are loaded by path."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
PHASE2 = HERE.parent / "phase2_offline"
PHASE3 = HERE.parent / "phase3_offline"
LOG_DIR = HERE / "synthetic_logs"
SCHEMA_VERSION = "r56.phase4.1"
COMPLETE = "SESSION_COMPLETE_SYNTHETIC"
INCOMPLETE = "SESSION_INCOMPLETE"

_TOP = frozenset(
    {
        "schema_version",
        "collected_at",
        "data_source",
        "session_id",
        "target_environment",
        "live_network_access",
        "timeout_enforcement",
        "live_socket_timeout",
        "summary_request",
        "pricing_request",
        "account_diagnostics",
        "pricing_diagnostics",
        "missing_evidence",
        "validation_warnings",
        "session_status",
        "error_code",
        "executable_order",
        "order_payload",
        "quote_freshness",
        "gbp_pip_value",
        "stake_to_unit_mapping",
        "financing",
        "pip_location",
        "executable_position_size",
        "strategy_profitability",
        "gbp_conversion_fallback",
        "home_conversion_request",
        "broker_evidence_complete",
        "phase2_adapters",
        "observed_clock_seconds",
        "observed_wall_seconds",
    }
)
_REQUEST = frozenset(
    {"sequence", "method", "scheme", "host", "port", "endpoint", "query", "result", "body", "redirects", "retries", "stream"}
)


class SessionRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _load(directory: Path, prefix: str, stem: str) -> Any:
    name = f"{prefix}_{stem}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, directory / f"{stem}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def new_session_id() -> str:
    return "r56-" + uuid.uuid4().hex


def run_offline(
    double: Any,
    *,
    credential: Any = None,
    clock: Any = None,
    log_dir: Path | None = None,
    session_id: str | None = None,
    collected_at: str | None = None,
    mode: str = "OFFLINE_TEST",
) -> dict[str, Any]:
    transport_mod = _load(HERE, "r56p4", "https_transport_candidate")
    credentials = _load(HERE, "r56p4", "credential_boundary")
    if mode != "OFFLINE_TEST":
        raise SessionRejected("OFFLINE_MODE_REQUIRED")
    if credential is None:
        credential = credentials.SyntheticCredential()
    flag = credentials.authorization_present(credential)
    if clock is None:
        clock = transport_mod.SessionClock(monotonic=transport_mod.ManualClock())
    session = session_id or new_session_id()
    collected = collected_at or _now()
    plan = _load(PHASE3, "r56p3", "readonly_request_plan")
    gate = _load(PHASE3, "r56p3", "readonly_request_gate")
    account_mod = _load(PHASE2, "r56p2", "account_diagnostics")
    pricing_mod = _load(PHASE2, "r56p2", "pricing_diagnostics")
    writer = _load(PHASE2, "r56p2", "diagnostic_writer")
    warnings: list[str] = []
    secrets: set[str] = set()
    summary_result = _not_sent(1, plan.SUMMARY_PATTERN)
    pricing_result = _not_sent(2, plan.PRICING_PATTERN)
    account_diag: Any = "NOT_PRODUCED"
    pricing_diag: Any = "NOT_PRODUCED"
    error = "NONE"
    wall_start = time.monotonic()
    transport = transport_mod.TransportSession(double, clock)
    try:
        approved = gate.approve(plan.summary_candidate(), step=1, prior=[])
        raw = transport.execute(approved, authorization_present=flag)
        summary_result = _accepted(approved, 1)
        try:
            summary_doc = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            error = "MALFORMED_JSON"
            summary_result["result"] = "REJECTED"
            return _finish(transport, clock, wall_start, collected, session, summary_result, pricing_result, account_diag, pricing_diag, warnings, secrets, error, log_dir)
        account_body, account_secrets = account_mod.build(json.loads(json.dumps(summary_doc)))
        secrets |= account_secrets
        account_diag = writer.stamp(account_body, data_source="SYNTHETIC_TEST_ONLY", session_id=session, collected_at=collected)
        warnings.extend(account_diag.get("validation_warnings") or [])
        if account_diag.get("outcome") != "DIAGNOSTIC_RECORDED":
            error = "SUMMARY_REJECTED"
            summary_result["result"] = "REJECTED"
            return _finish(transport, clock, wall_start, collected, session, summary_result, pricing_result, account_diag, "NOT_PRODUCED", warnings, secrets, error, log_dir)
        if hasattr(double, "note_summary_done"):
            double.note_summary_done(clock)
        approved_pricing = gate.approve(plan.pricing_candidate(), step=2, prior=["summary"])
        raw_pricing = transport.execute(approved_pricing, authorization_present=flag)
        pricing_result = _accepted(approved_pricing, 2)
        try:
            pricing_doc = json.loads(raw_pricing.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            error = "MALFORMED_JSON"
            pricing_result["result"] = "REJECTED"
            return _finish(transport, clock, wall_start, collected, session, summary_result, pricing_result, account_diag, "NOT_PRODUCED", warnings, secrets, error, log_dir)
        price_bodies, price_secrets = pricing_mod.build(json.loads(json.dumps(pricing_doc)))
        secrets |= price_secrets
        pricing_diag = [
            writer.stamp(body, data_source="SYNTHETIC_TEST_ONLY", session_id=session, collected_at=collected)
            for body in price_bodies
        ]
        for item in pricing_diag:
            warnings.extend(item.get("validation_warnings") or [])
        if not pricing_diag or any(item.get("outcome") != "DIAGNOSTIC_RECORDED" for item in pricing_diag):
            error = "PRICING_REJECTED"
            pricing_result["result"] = "REJECTED"
            return _finish(transport, clock, wall_start, collected, session, summary_result, pricing_result, account_diag, pricing_diag, warnings, secrets, error, log_dir)
        return _finish(
            transport,
            clock,
            wall_start,
            collected,
            session,
            summary_result,
            pricing_result,
            account_diag,
            pricing_diag,
            warnings,
            secrets,
            "NONE",
            log_dir,
            status=COMPLETE,
        )
    except gate.GateRejected as exc:
        error = exc.code
    except transport_mod.TransportRejected as exc:
        error = exc.code
        if summary_result["result"] == "SYNTHETIC_RESPONSE_ACCEPTED" and pricing_result["result"] == "NOT_SENT":
            pricing_result = _rejected(2, plan.PRICING_PATTERN)
        elif summary_result["result"] == "NOT_SENT":
            summary_result = _rejected(1, plan.SUMMARY_PATTERN)
    except credentials.CredentialRejected as exc:
        error = exc.code
    except Exception:
        error = "EXCEPTION_CONTAINED"
        warnings.append("exception_contained")
    return _finish(transport, clock, wall_start, collected, session, summary_result, pricing_result, account_diag, pricing_diag, warnings, secrets, error, log_dir)


def _finish(
    transport: Any,
    clock: Any,
    wall_start: float,
    collected: str,
    session: str,
    summary_result: dict,
    pricing_result: dict,
    account_diag: Any,
    pricing_diag: Any,
    warnings: list[str],
    secrets: set[str],
    error: str,
    log_dir: Path | None,
    *,
    status: str = INCOMPLETE,
) -> dict[str, Any]:
    transport.close()
    record = _record(
        collected,
        session,
        summary_result,
        pricing_result,
        account_diag,
        pricing_diag,
        warnings,
        error,
        status=status,
        clock_seconds=f"{clock.monotonic() - clock.session_started:.4f}",
        wall_seconds=f"{time.monotonic() - wall_start:.4f}",
    )
    text = json.dumps(record, indent=2, sort_keys=True)
    credentials = _load(HERE, "r56p4", "credential_boundary")
    if credentials.SYNTHETIC_TOKEN in text or credentials.SYNTHETIC_ACCOUNT_ID in text or "Bearer " in text:
        record = _record(
            collected,
            session,
            _not_sent(1, "/v3/accounts/{accountID}/summary"),
            _not_sent(2, "/v3/accounts/{accountID}/pricing"),
            "NOT_PRODUCED",
            "NOT_PRODUCED",
            ["sensitive_output_blocked"],
            "SENSITIVE_OUTPUT_BLOCKED",
            status=INCOMPLETE,
            clock_seconds="REDACTED",
            wall_seconds="REDACTED",
        )
        text = json.dumps(record, indent=2, sort_keys=True)
    if record["session_status"] == COMPLETE and record["error_code"] != "NONE":
        record["session_status"] = INCOMPLETE
        record["error_code"] = "FALSE_SUCCESS_BLOCKED"
        text = json.dumps(record, indent=2, sort_keys=True)
    path = _allocate(_log_dir(log_dir), session)
    path.write_text(text + "\n", encoding="utf-8")
    return record


def _record(
    collected: str,
    session: str,
    summary_result: dict,
    pricing_result: dict,
    account_diag: Any,
    pricing_diag: Any,
    warnings: list[str],
    error: str,
    *,
    status: str,
    clock_seconds: str,
    wall_seconds: str,
) -> dict[str, Any]:
    transport_mod = _load(HERE, "r56p4", "https_transport_candidate")
    missing = [
        "QUOTE_FRESHNESS_NOT_VERIFIED",
        "GBP_PIP_VALUE_UNVERIFIED",
        "STAKE_TO_UNIT_MAPPING_NOT_VERIFIED",
        "FINANCING_NOT_VERIFIED",
        "PIP_LOCATION_NOT_ESTABLISHED",
    ]
    if isinstance(account_diag, dict) and account_diag.get("home_currency") == "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED":
        missing.append("ACCOUNT_HOME_CURRENCY_API_UNVERIFIED")
    if pricing_diag == "NOT_PRODUCED" or _conversion_missing(pricing_diag):
        missing.append("HOME_CONVERSION_NOT_VERIFIED")
    record = {
        "schema_version": SCHEMA_VERSION,
        "collected_at": collected,
        "data_source": "SYNTHETIC_TEST_ONLY",
        "session_id": session,
        "target_environment": transport_mod.TARGET_ENVIRONMENT,
        "live_network_access": transport_mod.LIVE_NETWORK_ACCESS,
        "timeout_enforcement": transport_mod.TIMEOUT_ENFORCEMENT,
        "live_socket_timeout": transport_mod.LIVE_SOCKET_TIMEOUT,
        "summary_request": summary_result,
        "pricing_request": pricing_result,
        "account_diagnostics": account_diag,
        "pricing_diagnostics": pricing_diag,
        "missing_evidence": missing,
        "validation_warnings": _unique(warnings),
        "session_status": status,
        "error_code": error,
        "executable_order": "NOT_PRODUCED",
        "order_payload": "NOT_PRODUCED",
        "quote_freshness": "QUOTE_FRESHNESS_NOT_VERIFIED",
        "gbp_pip_value": "GBP_PIP_VALUE_UNVERIFIED",
        "stake_to_unit_mapping": "STAKE_TO_UNIT_MAPPING_NOT_VERIFIED",
        "financing": "FINANCING_NOT_VERIFIED",
        "pip_location": "NOT_ESTABLISHED",
        "executable_position_size": "NOT_CALCULATED",
        "strategy_profitability": "NOT_ESTABLISHED",
        "gbp_conversion_fallback": "NOT_USED",
        "home_conversion_request": "NOT_REQUESTED",
        "broker_evidence_complete": False,
        "phase2_adapters": "REUSED",
        "observed_clock_seconds": clock_seconds,
        "observed_wall_seconds": wall_seconds,
    }
    if set(record) != _TOP or set(summary_result) != _REQUEST or set(pricing_result) != _REQUEST:
        raise SessionRejected("ALLOWLIST_REJECTED")
    return record


def _conversion_missing(pricing_diag: Any) -> bool:
    if not isinstance(pricing_diag, list):
        return True
    return any(item.get("home_conversion") == "HOME_CONVERSION_NOT_VERIFIED" for item in pricing_diag)


def _accepted(approved: dict, sequence: int) -> dict:
    return {
        "sequence": sequence,
        "method": "GET",
        "scheme": "https",
        "host": approved["host"],
        "port": 443,
        "endpoint": approved["endpoint"],
        "query": approved["query"],
        "result": "SYNTHETIC_RESPONSE_ACCEPTED",
        "body": "NONE",
        "redirects": False,
        "retries": 0,
        "stream": False,
    }


def _rejected(sequence: int, endpoint: str) -> dict:
    row = _not_sent(sequence, endpoint)
    row["result"] = "REJECTED"
    return row


def _not_sent(sequence: int, endpoint: str) -> dict:
    return {
        "sequence": sequence,
        "method": "GET",
        "scheme": "https",
        "host": "api-fxtrade.oanda.com",
        "port": 443,
        "endpoint": endpoint,
        "query": {},
        "result": "NOT_SENT",
        "body": "NONE",
        "redirects": False,
        "retries": 0,
        "stream": False,
    }


def _log_dir(path: Path | None) -> Path:
    target = LOG_DIR if path is None else Path(path)
    resolved = target.resolve()
    try:
        resolved.relative_to(HERE.resolve() / "synthetic_logs")
    except ValueError:
        raise SessionRejected("LOG_PATH_OUTSIDE") from None
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _allocate(log_dir: Path, session_id: str) -> Path:
    token = session_id.replace("-", "")
    for number in range(1, 10000):
        path = log_dir / f"r56-phase4-{token}-{number:04d}.json"
        try:
            handle = path.open("x", encoding="utf-8")
        except FileExistsError:
            continue
        handle.close()
        return path
    raise SessionRejected("LOG_NAME_EXHAUSTED")


def _unique(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

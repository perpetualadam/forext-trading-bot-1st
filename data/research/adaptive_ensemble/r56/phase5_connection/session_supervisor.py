"""Parent supervisor. The wall-clock deadline lives here, and a late child is terminated."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WORKER = HERE / "isolated_worker.py"
LOG_DIR = HERE / "synthetic_logs"
COMPLETE = "SESSION_COMPLETE_SYNTHETIC"
INCOMPLETE = "SESSION_INCOMPLETE"
ACCOUNT_ID_RE = re.compile(r"\d{3}-\d{3}-\d{3,}-\d{3}")
_SAFE_ENV = ("SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATH", "PATHEXT", "TEMP", "TMP")
_REQUEST = frozenset({"sequence", "method", "scheme", "host", "port", "endpoint", "query", "result", "body", "redirects", "retries", "stream"})
_TOP = frozenset(
    {
        "schema_version",
        "collected_at",
        "data_source",
        "session_id",
        "target_environment",
        "live_network_access",
        "confirmation",
        "network_permitted",
        "process_isolation",
        "per_operation_timeout",
        "per_request_deadline_seconds",
        "session_deadline_seconds",
        "child_termination",
        "child_alive",
        "children_started",
        "observed_wall_seconds",
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
        "raw_response_persisted",
        "phase2_adapters",
    }
)

LAST_JOBS: list[dict[str, Any]] = []
LAST_ARGV: list[str] = []
LAST_PROC: subprocess.Popen[bytes] | None = None


class SupervisorRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class SessionBudget:
    """At most two child starts. The third reserve fails closed."""

    def __init__(self) -> None:
        self.started = 0

    def reserve(self) -> None:
        if self.started >= 2:
            raise SupervisorRejected("REQUEST_LIMIT")
        self.started += 1


def _load(stem: str) -> Any:
    name = f"r56p5_{stem}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, HERE / f"{stem}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def child_env() -> dict[str, str]:
    """A minimal environment. Proxy variables and credential variables are not copied."""
    env = {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    for key in _SAFE_ENV:
        value = os.environ.get(key)
        if value:
            env[key] = value
    for banned in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy"):
        env.pop(banned, None)
    return env


def child_argv() -> list[str]:
    return [sys.executable, "-B", str(WORKER), "--offline-worker"]


def new_session_id() -> str:
    return "r56-" + uuid.uuid4().hex


def run_offline(
    *,
    answer: str,
    credential: object,
    summary_document: dict | None = None,
    pricing_document: dict | None = None,
    summary_status: int = 200,
    pricing_status: int = 200,
    summary_body_text: str | None = None,
    pricing_body_text: str | None = None,
    summary_fill: int = 0,
    stall: str | None = None,
    stall_step: str = "summary",
    ignore_seconds: float = 10.0,
    request_deadline: float = 5.0,
    session_deadline: float = 15.0,
    log_dir: Path | None = None,
    session_id: str | None = None,
    collected_at: str | None = None,
) -> dict[str, Any]:
    global LAST_JOBS, LAST_ARGV
    confirmation_mod = _load("operator_confirmation")
    credentials = _load("credential_gate")
    fixtures = _load("synthetic_fixtures")
    label = str(LOG_DIR if log_dir is None else log_dir)
    screen = confirmation_mod.render_screen(log_destination=label)
    confirmation = confirmation_mod.confirm_synthetic(answer, screen=screen)
    if confirmation.get("network_permitted") is not False:
        raise SupervisorRejected("NETWORK_PERMITTED_REJECTED")
    credentials.accept_offline(credential)
    if request_deadline <= 0 or request_deadline > 5.0 or session_deadline <= 0 or session_deadline > 15.0:
        raise SupervisorRejected("DEADLINE_ABOVE_CAP")
    target = _log_dir(log_dir)
    session = session_id or new_session_id()
    collected = collected_at or _now()
    summary_doc = fixtures.summary_document() if summary_document is None else summary_document
    pricing_doc = fixtures.pricing_document() if pricing_document is None else pricing_document
    budget = SessionBudget()
    LAST_JOBS = []
    wall_start = time.monotonic()
    summary_payload: dict[str, Any] | None = None
    pricing_payload: dict[str, Any] | None = None
    error = "NONE"
    terminated = False
    alive = False
    try:
        summary_payload, summary_term, summary_alive = _spawn(
            step="summary",
            prior=[],
            document=summary_doc,
            status=summary_status,
            body_text=summary_body_text,
            fill=summary_fill,
            stall=stall if stall_step == "summary" else None,
            ignore_seconds=ignore_seconds,
            request_deadline=request_deadline,
            session_deadline=session_deadline,
            session_started=wall_start,
            session_id=session,
            collected_at=collected,
            budget=budget,
        )
        terminated = summary_term
        alive = summary_alive
        if summary_term:
            error = "CHILD_TERMINATED"
        elif summary_payload is None:
            error = "CHILD_CRASHED"
        elif summary_payload.get("error_code") != "NONE":
            error = str(summary_payload["error_code"])
        elif not isinstance(summary_payload.get("diagnostics"), dict) or summary_payload["diagnostics"].get("outcome") != "DIAGNOSTIC_RECORDED":
            error = "SUMMARY_REJECTED"
        else:
            pricing_payload, pricing_term, pricing_alive = _spawn(
                step="pricing",
                prior=["summary"],
                document=pricing_doc,
                status=pricing_status,
                body_text=pricing_body_text,
                fill=0,
                stall=stall if stall_step == "pricing" else None,
                ignore_seconds=ignore_seconds,
                request_deadline=request_deadline,
                session_deadline=session_deadline,
                session_started=wall_start,
                session_id=session,
                collected_at=collected,
                budget=budget,
            )
            terminated = pricing_term
            alive = pricing_alive
            if pricing_term:
                error = "CHILD_TERMINATED"
            elif pricing_payload is None:
                error = "CHILD_CRASHED"
            elif pricing_payload.get("error_code") != "NONE":
                error = str(pricing_payload["error_code"])
            elif not isinstance(pricing_payload.get("diagnostics"), list):
                error = "PRICING_REJECTED"
    except SupervisorRejected as exc:
        error = exc.code
    elapsed = time.monotonic() - wall_start
    record = _record(
        collected,
        session,
        summary_payload,
        pricing_payload,
        error=error,
        terminated=terminated,
        alive=alive,
        children=budget.started,
        elapsed=elapsed,
        request_deadline=request_deadline,
        session_deadline=session_deadline,
    )
    text = json.dumps(record, indent=2, sort_keys=True)
    if _sensitive(text) or (record["session_status"] == COMPLETE and record["error_code"] != "NONE"):
        record = _record(
            collected,
            session,
            None,
            None,
            error="SENSITIVE_OUTPUT_BLOCKED" if _sensitive(text) else "FALSE_SUCCESS_BLOCKED",
            terminated=terminated,
            alive=alive,
            children=budget.started,
            elapsed=elapsed,
            request_deadline=request_deadline,
            session_deadline=session_deadline,
        )
        text = json.dumps(record, indent=2, sort_keys=True)
    path = _allocate(target, session)
    path.write_text(text + "\n", encoding="utf-8")
    LAST_ARGV = child_argv()
    return record


def _spawn(
    *,
    step: str,
    prior: list[str],
    document: dict,
    status: int,
    body_text: str | None,
    fill: int,
    stall: str | None,
    ignore_seconds: float,
    request_deadline: float,
    session_deadline: float,
    session_started: float,
    session_id: str,
    collected_at: str,
    budget: SessionBudget,
) -> tuple[dict[str, Any] | None, bool, bool]:
    global LAST_PROC
    remaining = session_deadline - (time.monotonic() - session_started)
    if remaining <= 0:
        raise SupervisorRejected("SESSION_DEADLINE")
    budget.reserve()
    job: dict[str, Any] = {
        "mode": "OFFLINE_TEST",
        "connector": "scripted",
        "confirmed": True,
        "network_permitted": False,
        "credential_classification": "SYNTHETIC_TEST_ONLY",
        "authorization_present": True,
        "step": step,
        "prior": prior,
        "session_id": session_id,
        "collected_at": collected_at,
        "document": document,
        "status": status,
        "request_deadline": request_deadline,
    }
    if body_text is not None:
        job["body_text"] = body_text
    if fill:
        job["fill"] = fill
    if stall:
        job["stall"] = stall
        job["ignore_seconds"] = ignore_seconds
    LAST_JOBS.append(job)
    argv = child_argv()
    env = child_env()
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=str(HERE),
    )
    LAST_PROC = proc
    timeout = min(request_deadline, remaining)
    terminated = False
    try:
        out, _err = proc.communicate(json.dumps(job).encode("utf-8"), timeout=timeout)
    except subprocess.TimeoutExpired:
        terminated = True
        proc.kill()
        out, _err = proc.communicate()
    alive = proc.poll() is None
    if terminated:
        return None, True, alive
    if alive:
        proc.kill()
        proc.wait(timeout=2)
        return None, True, proc.poll() is None
    text = out.decode("utf-8", errors="replace")
    if _sensitive(text):
        return _child_error("SENSITIVE_OUTPUT_BLOCKED", step), False, False
    if not text.strip():
        code = "CHILD_CRASHED" if proc.returncode not in (0, None) else "MALFORMED_CHILD_RESULT"
        return _child_error(code, step), False, False
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return _child_error("MALFORMED_CHILD_RESULT", step), False, False
    if not isinstance(payload, dict) or payload.get("data_source") != "SYNTHETIC_TEST_ONLY":
        return _child_error("MALFORMED_CHILD_RESULT", step), False, False
    if payload.get("step") != step or payload.get("executable_order") != "NOT_PRODUCED":
        return _child_error("MALFORMED_CHILD_RESULT", step), False, False
    return payload, False, False


def _child_error(code: str, step: str) -> dict[str, Any]:
    transport = _load("restricted_https_transport")
    endpoint = transport.SUMMARY_PATTERN if step == "summary" else transport.PRICING_PATTERN
    return {
        "schema_version": "r56.phase5.child.1",
        "data_source": "SYNTHETIC_TEST_ONLY",
        "step": step,
        "result": "REJECTED",
        "endpoint": endpoint,
        "diagnostics": "NOT_PRODUCED",
        "error_code": code,
        "validation_warnings": [],
        "missing_evidence": [],
        "executable_order": "NOT_PRODUCED",
    }


def _record(
    collected: str,
    session: str,
    summary_payload: dict[str, Any] | None,
    pricing_payload: dict[str, Any] | None,
    *,
    error: str,
    terminated: bool,
    alive: bool,
    children: int,
    elapsed: float,
    request_deadline: float,
    session_deadline: float,
) -> dict[str, Any]:
    transport = _load("restricted_https_transport")
    account = summary_payload.get("diagnostics") if summary_payload else "NOT_PRODUCED"
    pricing = pricing_payload.get("diagnostics") if pricing_payload else "NOT_PRODUCED"
    if account is None:
        account = "NOT_PRODUCED"
    if pricing is None:
        pricing = "NOT_PRODUCED"
    warnings: list[str] = []
    for payload in (summary_payload, pricing_payload):
        if isinstance(payload, dict):
            warnings.extend(payload.get("validation_warnings") or [])
    missing = [
        "QUOTE_FRESHNESS_NOT_VERIFIED",
        "GBP_PIP_VALUE_UNVERIFIED",
        "STAKE_TO_UNIT_MAPPING_NOT_VERIFIED",
        "FINANCING_NOT_VERIFIED",
        "PIP_LOCATION_NOT_ESTABLISHED",
        "HOME_CONVERSION_NOT_VERIFIED",
    ]
    if isinstance(account, dict) and account.get("home_currency") == "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED":
        missing.append("ACCOUNT_HOME_CURRENCY_API_UNVERIFIED")
    status = COMPLETE if error == "NONE" and terminated is False and alive is False else INCOMPLETE
    if alive:
        error = "CHILD_CLEANUP_FAILED"
        status = INCOMPLETE
    record = {
        "schema_version": "r56.phase5.1",
        "collected_at": collected,
        "data_source": "SYNTHETIC_TEST_ONLY",
        "session_id": session,
        "target_environment": transport.TARGET_ENVIRONMENT,
        "live_network_access": transport.LIVE_NETWORK_ACCESS,
        "confirmation": "CONFIRMED_SYNTHETIC",
        "network_permitted": False,
        "process_isolation": "CHILD_PROCESS",
        "per_operation_timeout": "SCRIPTED_CONNECTOR_DOES_NOT_BLOCK",
        "per_request_deadline_seconds": request_deadline,
        "session_deadline_seconds": session_deadline,
        "child_termination": "TERMINATED" if terminated else "NOT_REQUIRED",
        "child_alive": bool(alive),
        "children_started": children,
        "observed_wall_seconds": f"{elapsed:.4f}",
        "summary_request": _request(1, transport.SUMMARY_PATTERN, {}, summary_payload),
        "pricing_request": _request(2, transport.PRICING_PATTERN, {"instruments": transport.INSTRUMENTS}, pricing_payload),
        "account_diagnostics": account,
        "pricing_diagnostics": pricing,
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
        "raw_response_persisted": False,
        "phase2_adapters": "REUSED",
    }
    if set(record) != _TOP:
        raise SupervisorRejected("ALLOWLIST_REJECTED")
    return record


def _request(sequence: int, endpoint: str, query: dict, payload: dict[str, Any] | None) -> dict[str, Any]:
    result = "NOT_SENT"
    if isinstance(payload, dict):
        result = str(payload.get("result") or "REJECTED")
    row = {
        "sequence": sequence,
        "method": "GET",
        "scheme": "https",
        "host": "api-fxtrade.oanda.com",
        "port": 443,
        "endpoint": endpoint,
        "query": query,
        "result": result,
        "body": "NONE",
        "redirects": False,
        "retries": 0,
        "stream": False,
    }
    if set(row) != _REQUEST:
        raise SupervisorRejected("ALLOWLIST_REJECTED")
    return row


def _sensitive(text: str) -> bool:
    if ACCOUNT_ID_RE.search(text):
        return True
    lowered = text.lower()
    if "synthetic-not-real" in lowered or "bearer " in lowered:
        return True
    return False


def _log_dir(path: Path | None) -> Path:
    target = LOG_DIR if path is None else Path(path)
    resolved = target.resolve()
    try:
        resolved.relative_to(HERE.resolve() / "synthetic_logs")
    except ValueError:
        raise SupervisorRejected("LOG_PATH_OUTSIDE") from None
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _allocate(log_dir: Path, session_id: str) -> Path:
    token = session_id.replace("-", "")
    for number in range(1, 10000):
        path = log_dir / f"r56-phase5-{token}-{number:04d}.json"
        try:
            handle = path.open("x", encoding="utf-8")
        except FileExistsError:
            continue
        handle.close()
        return path
    raise SupervisorRejected("LOG_NAME_EXHAUSTED")


def _unique(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

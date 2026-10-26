"""Parent for two supervised GET workers. The wall clock and the IPC pipe stay here."""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WORKER = HERE / "diagnostic_worker.py"
PHASE5 = HERE.parent / "phase5_connection"
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
        "network_attempted",
        "broker_response_received",
        "real_session_source_enablement",
        "process_isolation",
        "per_request_deadline_seconds",
        "session_deadline_seconds",
        "child_termination",
        "child_alive",
        "children_started",
        "observed_wall_seconds",
        "ipc_write_closed",
        "ipc_child_closed",
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
        "record_persisted",
        "phase2_adapters",
    }
)

LAST_ARGV: list[str] = []
LAST_PUBLIC: list[dict[str, Any]] = []
LAST_IPC_WRITE_CLOSED = False
LAST_PROC: subprocess.Popen[bytes] | None = None
LAST_CHILD_RESULTS: list[dict[str, Any]] = []
LAST_ISSUER: Any = None
LAST_TRACKER: Any = None


class SupervisorRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class SessionBudget:
    def __init__(self) -> None:
        self.started = 0

    def reserve(self) -> None:
        if self.started >= 2:
            raise SupervisorRejected("REQUEST_LIMIT")
        self.started += 1


class ChildTracker:
    """Parent-owned child processes. cleanup() is safe to call more than once."""

    def __init__(self) -> None:
        self.procs: list[subprocess.Popen[bytes]] = []

    def add(self, proc: subprocess.Popen[bytes]) -> None:
        self.procs.append(proc)

    def cleanup(self) -> int:
        killed = 0
        for proc in self.procs:
            try:
                if proc.stdin is not None and not proc.stdin.closed:
                    proc.stdin.close()
            except (AttributeError, OSError, ValueError):
                pass
            if proc.poll() is None:
                try:
                    proc.kill()
                    killed += 1
                except OSError:
                    pass
            try:
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except OSError:
                    pass
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
            for pipe in (proc.stdout, proc.stderr):
                try:
                    if pipe is not None and not pipe.closed:
                        pipe.close()
                except (AttributeError, OSError, ValueError):
                    pass
        return killed


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


def child_env() -> dict[str, str]:
    env = {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1", "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    for key in _SAFE_ENV:
        value = os.environ.get(key)
        if value:
            env[key] = value
    for banned in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy"):
        env.pop(banned, None)
    return env


def child_argv() -> list[str]:
    return [sys.executable, "-B", str(WORKER), "--offline-worker"]


def authenticated_child_argv() -> list[str]:
    """Harness worker. The seam tripwires HTTPSConnection and cannot open a real socket."""
    return [sys.executable, "-B", str(WORKER), "--authenticated-worker", "--harness-transport"]


def real_child_argv() -> list[str]:
    """Future real worker. No harness flag. The source switch still refuses this process."""
    return [sys.executable, "-B", str(WORKER), "--authenticated-worker"]


def new_session_id() -> str:
    return "r56-" + uuid.uuid4().hex


def _marker(credential: object) -> str:
    credentials = _load(PHASE5, "r56p5", "credential_gate")
    if credential.__class__ is not credentials.SyntheticCredential:
        raise SupervisorRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
    if getattr(credential, "classification", None) != "SYNTHETIC_TEST_ONLY":
        raise SupervisorRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
    marker = getattr(credential, "token", "")
    account_id = getattr(credential, "account_id", "")
    if not isinstance(marker, str) or not marker.startswith("SYNTHETIC-") or "NOT-REAL" not in marker:
        raise SupervisorRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
    if account_id != credentials.SYNTHETIC_ACCOUNT_ID:
        raise SupervisorRejected("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
    return marker


def run_offline(
    *,
    answer: str,
    credential: object,
    summary_fixture: str = "summary",
    pricing_fixture: str = "pricing",
    summary_status: int = 200,
    pricing_status: int = 200,
    summary_body_text: str | None = None,
    summary_fill: int = 0,
    pricing_bid: str | None = None,
    stall: str | None = None,
    stall_step: str = "summary",
    ignore_seconds: float = 10.0,
    request_deadline: float = 5.0,
    session_deadline: float = 15.0,
    tls_policy: dict | None = None,
    proxy_from_environment: bool = False,
    log_dir: Path | None = None,
    session_id: str | None = None,
    collected_at: str | None = None,
) -> dict[str, Any]:
    global LAST_PUBLIC
    confirmation = _load(PHASE5, "r56p5", "operator_confirmation")
    label = str(LOG_DIR if log_dir is None else log_dir)
    screen = confirmation.render_screen(log_destination=label)
    agreed = confirmation.confirm_synthetic(answer, screen=screen)
    if agreed.get("network_permitted") is not False:
        raise SupervisorRejected("NETWORK_PERMITTED_REJECTED")
    marker = _marker(credential)
    try:
        if request_deadline <= 0 or request_deadline > 5 or session_deadline <= 0 or session_deadline > 15:
            raise SupervisorRejected("DEADLINE_ABOVE_CAP")
        target = _log_dir(log_dir)
        session = session_id or new_session_id()
        collected = collected_at or _now()
        budget = SessionBudget()
        LAST_PUBLIC = []
        wall_start = time.monotonic()
        summary_payload = None
        pricing_payload = None
        error = "NONE"
        terminated = False
        alive = False
        ipc_write_closed = False
        ipc_child_closed = False
        try:
            summary_payload, summary_term, summary_alive, write_closed, child_closed = _spawn(
                step="summary",
                prior=[],
                fixture=summary_fixture,
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
                marker=marker,
                budget=budget,
                tls_policy=tls_policy,
                proxy_from_environment=proxy_from_environment,
                pricing_bid=None,
            )
            terminated = summary_term
            alive = summary_alive
            ipc_write_closed = write_closed
            ipc_child_closed = child_closed
            if summary_term:
                error = "CHILD_TERMINATED"
            elif summary_payload is None:
                error = "CHILD_CRASHED"
            elif summary_payload.get("error_code") != "NONE":
                error = str(summary_payload["error_code"])
            elif not isinstance(summary_payload.get("diagnostics"), dict) or summary_payload["diagnostics"].get("outcome") != "DIAGNOSTIC_RECORDED":
                error = "SUMMARY_REJECTED"
            else:
                pricing_payload, pricing_term, pricing_alive, write_closed, child_closed = _spawn(
                    step="pricing",
                    prior=["summary"],
                    fixture=pricing_fixture,
                    status=pricing_status,
                    body_text=None,
                    fill=0,
                    stall=stall if stall_step == "pricing" else None,
                    ignore_seconds=ignore_seconds,
                    request_deadline=request_deadline,
                    session_deadline=session_deadline,
                    session_started=wall_start,
                    session_id=session,
                    collected_at=collected,
                    marker=marker,
                    budget=budget,
                    tls_policy=tls_policy,
                    proxy_from_environment=proxy_from_environment,
                    pricing_bid=pricing_bid,
                )
                terminated = pricing_term
                alive = pricing_alive
                ipc_write_closed = write_closed
                ipc_child_closed = child_closed and ipc_child_closed
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
        record = _record(
            collected,
            session,
            summary_payload,
            pricing_payload,
            error=error,
            terminated=terminated,
            alive=alive,
            children=budget.started,
            elapsed=time.monotonic() - wall_start,
            request_deadline=request_deadline,
            session_deadline=session_deadline,
            ipc_write_closed=ipc_write_closed,
            ipc_child_closed=ipc_child_closed,
        )
        text = json.dumps(record, indent=2, sort_keys=True)
        exact = _exact_secrets(marker)
        if _sensitive(text, marker, exact) or (record["session_status"] == COMPLETE and record["error_code"] != "NONE"):
            record = _record(
                collected,
                session,
                None,
                None,
                error="SENSITIVE_OUTPUT_BLOCKED" if _sensitive(text, marker, exact) else "FALSE_SUCCESS_BLOCKED",
                terminated=terminated,
                alive=alive,
                children=budget.started,
                elapsed=time.monotonic() - wall_start,
                request_deadline=request_deadline,
                session_deadline=session_deadline,
                ipc_write_closed=ipc_write_closed,
                ipc_child_closed=False,
            )
            text = json.dumps(record, indent=2, sort_keys=True)
        record["record_persisted"] = True
        text = json.dumps(record, indent=2, sort_keys=True)
        path = _allocate(target, session)
        try:
            _persist_record(path, text)
        except Exception:
            _mark_persistence_failed(record, "RECORD_PERSISTENCE_FAILED")
            _drop_empty_record(path)
        return record
    finally:
        marker = ""


def _spawn(
    *,
    step: str,
    prior: list[str],
    fixture: str,
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
    marker: str,
    budget: SessionBudget,
    tls_policy: dict | None,
    proxy_from_environment: bool,
    pricing_bid: str | None,
) -> tuple[dict[str, Any] | None, bool, bool, bool, bool]:
    global LAST_ARGV, LAST_IPC_WRITE_CLOSED, LAST_PROC
    remaining = session_deadline - (time.monotonic() - session_started)
    if remaining <= 0:
        raise SupervisorRejected("SESSION_DEADLINE")
    budget.reserve()
    public: dict[str, Any] = {
        "schema": "r56.phase6.ipc.1",
        "mode": "OFFLINE_TEST",
        "step": step,
        "prior": prior,
        "session_id": session_id,
        "collected_at": collected_at,
        "fixture": fixture,
        "status": status,
        "request_deadline": request_deadline,
    }
    if body_text is not None:
        public["body_text"] = body_text
    if fill:
        public["fill"] = fill
    if stall:
        public["stall"] = stall
        public["ignore_seconds"] = ignore_seconds
    if tls_policy is not None:
        public["tls_policy"] = tls_policy
    if proxy_from_environment:
        public["proxy_from_environment"] = True
    if pricing_bid is not None:
        public["pricing_bid"] = pricing_bid
    LAST_PUBLIC.append(public)
    ipc = _load(HERE, "r56p6", "credential_ipc")
    frame = ipc.encode(
        {
            **public,
            "credential": {
                "classification": "SYNTHETIC_TEST_ONLY",
                "account_selector": "SYNTHETIC_PIN",
                "marker": marker,
            },
        }
    )
    argv = child_argv()
    LAST_ARGV = argv
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=child_env(),
        cwd=str(HERE),
    )
    LAST_PROC = proc
    assert proc.stdin is not None
    proc.stdin.write(frame)
    proc.stdin.close()
    del frame
    write_closed = False
    try:
        proc.stdin.write(b"x")
    except (ValueError, OSError):
        write_closed = True
    LAST_IPC_WRITE_CLOSED = write_closed
    timeout = min(request_deadline, remaining)
    terminated = False
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        terminated = True
        proc.kill()
        out, err = proc.communicate()
    del err
    alive = proc.poll() is None
    if terminated:
        return None, True, alive, write_closed, False
    text = out.decode("utf-8", errors="replace")
    if _sensitive(text, marker, _exact_secrets(marker)):
        return _child_error("SENSITIVE_OUTPUT_BLOCKED", step), False, False, write_closed, False
    if not text.strip():
        code = "CHILD_CRASHED" if proc.returncode not in (0, None) else "MALFORMED_CHILD_RESULT"
        return _child_error(code, step), False, False, write_closed, False
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return _child_error("MALFORMED_CHILD_RESULT", step), False, False, write_closed, False
    if not isinstance(payload, dict) or payload.get("data_source") != "SYNTHETIC_TEST_ONLY":
        return _child_error("MALFORMED_CHILD_RESULT", step), False, False, write_closed, False
    if payload.get("step") != step or payload.get("executable_order") != "NOT_PRODUCED":
        return _child_error("MALFORMED_CHILD_RESULT", step), False, False, write_closed, False
    return payload, False, False, write_closed, payload.get("ipc_closed") is True


def _child_error(code: str, step: str) -> dict[str, Any]:
    endpoint = "/v3/accounts/{accountID}/summary" if step == "summary" else "/v3/accounts/{accountID}/pricing"
    return {
        "schema_version": "r56.phase6.child.1",
        "data_source": "SYNTHETIC_TEST_ONLY",
        "step": step,
        "result": "REJECTED",
        "endpoint": endpoint,
        "diagnostics": "NOT_PRODUCED",
        "error_code": code,
        "validation_warnings": [],
        "missing_evidence": [],
        "executable_order": "NOT_PRODUCED",
        "ipc_closed": False,
        "authorization_accepted": False,
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
    ipc_write_closed: bool,
    ipc_child_closed: bool,
    dispatch_mode: str = "HARNESS",
    session_authorised: bool = False,
    network_attempted: bool = False,
    broker_response_received: bool = False,
) -> dict[str, Any]:
    pins = _load(PHASE5, "r56p5", "restricted_https_transport")
    gate = _load(HERE, "r56p6", "live_session_gate")
    persisted_authorised = (
        session_authorised is True and dispatch_mode == "REAL" and gate.REAL_SESSION_SOURCE_ENABLEMENT is True
    )
    facts = _session_facts(
        authorised=persisted_authorised,
        attempted=network_attempted,
        received=broker_response_received,
    )
    account = summary_payload.get("diagnostics") if isinstance(summary_payload, dict) else "NOT_PRODUCED"
    pricing = pricing_payload.get("diagnostics") if isinstance(pricing_payload, dict) else "NOT_PRODUCED"
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
    if alive and error == "NONE":
        error = "CHILD_CLEANUP_FAILED"
    source_label, confirmation_label, network_label, success_label, successful = _outcome_labels(
        facts,
        error=error,
        terminated=terminated,
        alive=alive,
        dispatch_mode=dispatch_mode,
        not_authorised=pins.LIVE_NETWORK_ACCESS,
    )
    status = success_label if successful else INCOMPLETE
    record = {
        "schema_version": "r56.phase6.1",
        "collected_at": collected,
        "data_source": source_label,
        "session_id": session,
        "target_environment": pins.TARGET_ENVIRONMENT,
        "live_network_access": network_label,
        "confirmation": confirmation_label,
        "network_permitted": facts["network_permitted"],
        "network_attempted": facts["network_attempted"],
        "broker_response_received": facts["broker_response_received"],
        "real_session_source_enablement": gate.REAL_SESSION_SOURCE_ENABLEMENT is True,
        "process_isolation": "CHILD_PROCESS",
        "per_request_deadline_seconds": request_deadline,
        "session_deadline_seconds": session_deadline,
        "child_termination": "TERMINATED" if terminated else "NOT_REQUIRED",
        "child_alive": bool(alive),
        "children_started": children,
        "observed_wall_seconds": f"{elapsed:.4f}",
        "ipc_write_closed": bool(ipc_write_closed),
        "ipc_child_closed": bool(ipc_child_closed),
        "summary_request": _request(1, pins.SUMMARY_PATTERN, {}, summary_payload),
        "pricing_request": _request(2, pins.PRICING_PATTERN, {"instruments": pins.INSTRUMENTS}, pricing_payload),
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
        "record_persisted": False,
        "phase2_adapters": "REUSED",
    }
    if set(record) != _TOP:
        raise SupervisorRejected("ALLOWLIST_REJECTED")
    return record


def _broker_received(payload: dict[str, Any] | None) -> bool:
    return isinstance(payload, dict) and payload.get("error_code") == "NONE" and payload.get("result") == "BROKER_RESPONSE_RECEIVED"


def _session_facts(*, authorised: bool, attempted: bool, received: bool) -> dict[str, bool]:
    """Parent-owned session facts. Child result labels are not an input."""
    if authorised is not True:
        return {"network_permitted": False, "network_attempted": False, "broker_response_received": False}
    attempted_now = attempted is True
    return {
        "network_permitted": True,
        "network_attempted": attempted_now,
        "broker_response_received": attempted_now and received is True,
    }


def _outcome_labels(facts: dict[str, bool], *, error: str, terminated: bool, alive: bool, dispatch_mode: str, not_authorised: str) -> tuple[str, str, str, str, bool]:
    """Labels follow parent facts. Authorisation alone is not a completed request."""
    if facts["network_permitted"]:
        source_label = "REAL_OANDA_LIVE_DIAGNOSTIC"
        confirmation_label = "OPERATOR_CONFIRMED_READ_ONLY"
        if not facts["network_attempted"]:
            network_label = "REAL_NETWORK_NOT_ATTEMPTED"
        elif facts["broker_response_received"] and error == "NONE" and terminated is False and alive is False:
            network_label = "REAL_NETWORK_COMPLETED"
        else:
            network_label = "REAL_NETWORK_NOT_COMPLETED"
        success_label = "SESSION_COMPLETE_REAL_DIAGNOSTIC"
        successful = error == "NONE" and terminated is False and alive is False and facts["broker_response_received"] is True
        return source_label, confirmation_label, network_label, success_label, successful
    if dispatch_mode == "REAL":
        return "REAL_SESSION_NOT_AUTHORISED", "NOT_CONFIRMED", not_authorised, "SESSION_INCOMPLETE", False
    successful = error == "NONE" and terminated is False and alive is False
    return "SYNTHETIC_TEST_ONLY", "CONFIRMED_SYNTHETIC", not_authorised, "SESSION_COMPLETE_SYNTHETIC", successful


def _source_for(dispatch_mode: str) -> str:
    if dispatch_mode == "REAL":
        return "REAL_OANDA_LIVE_DIAGNOSTIC"
    if dispatch_mode == "HARNESS":
        return "SYNTHETIC_TEST_ONLY"
    raise SupervisorRejected("MODE_REJECTED")


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


def _exact_secrets(marker: str) -> tuple[str, ...]:
    pins = _load(PHASE5, "r56p5", "restricted_https_transport")
    values: list[str] = []
    if isinstance(marker, str) and marker:
        values.extend((marker, "Bearer " + marker, "Authorization: Bearer " + marker))
    pin = getattr(pins, "SYNTHETIC_ACCOUNT_ID", "")
    if isinstance(pin, str) and pin:
        values.append(pin)
    return tuple(values)


def _sensitive(text: str, marker: str, exact: tuple[str, ...] = ()) -> bool:
    ipc = _load(HERE, "r56p6", "credential_ipc")
    if ipc.contains_exact(text, (marker, *exact)):
        return True
    if ACCOUNT_ID_RE.search(text):
        return True
    return False


def _log_dir(path: Path | None, *, dispatch_mode: str = "HARNESS") -> Path:
    synthetic = (HERE / "synthetic_logs").resolve()
    real_root = (HERE / "real_diagnostic_logs").resolve()
    if dispatch_mode == "REAL":
        root = real_root
    elif dispatch_mode == "HARNESS":
        root = synthetic
    else:
        raise SupervisorRejected("MODE_REJECTED")
    target = root if path is None else Path(path)
    resolved = target.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise SupervisorRejected("LOG_PATH_OUTSIDE") from None
    if dispatch_mode == "REAL":
        try:
            resolved.relative_to(synthetic)
        except ValueError:
            pass
        else:
            raise SupervisorRejected("LOG_PATH_OUTSIDE")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _persist_record(path: Path, text: str) -> None:
    """One write of an already sanitised record. Callers do not retry this."""
    path.write_text(text + "\n", encoding="utf-8")


def _drop_empty_record(path: Path | None) -> None:
    if path is None:
        return
    try:
        if path.is_file() and path.stat().st_size == 0:
            path.unlink()
    except OSError:
        pass


def _mark_persistence_failed(record: dict[str, Any], code: str) -> None:
    """The request rows stay as they were. The session itself did not persist."""
    record["error_code"] = code
    record["session_status"] = INCOMPLETE
    record["record_persisted"] = False
    if record.get("live_network_access") == "REAL_NETWORK_COMPLETED":
        record["live_network_access"] = "REAL_NETWORK_NOT_COMPLETED"


def _allocate(log_dir: Path, session_id: str) -> Path:
    token = session_id.replace("-", "")
    for number in range(1, 10000):
        path = log_dir / f"r56-phase6-{token}-{number:04d}.json"
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


def prepare_real_session(*args: object, **kwargs: object) -> None:
    gate = _load(HERE, "r56p6", "live_session_gate")
    gate.prepare_real_session(*args, **kwargs)


def dispatch_contract(
    mode: str,
    *,
    session_id: str,
    step: str,
    request_deadline: float = 5.0,
    session_deadline: float = 15.0,
) -> dict[str, Any]:
    """Describe one dispatch. This does not issue a token and does not start a process."""
    gate = _load(HERE, "r56p6", "live_session_gate")
    if mode == "HARNESS":
        argv = authenticated_child_argv()
        ipc_mode = "AUTHENTICATED_HARNESS"
        capability_mode = "HARNESS_SESSION"
    elif mode == "REAL":
        argv = real_child_argv()
        ipc_mode = "REAL_SESSION"
        capability_mode = "REAL_SESSION"
    else:
        raise SupervisorRejected("MODE_REJECTED")
    harness_flag = "--harness-transport" in argv
    if mode == "REAL" and (harness_flag or ipc_mode != "REAL_SESSION" or capability_mode != "REAL_SESSION"):
        raise SupervisorRejected("MODE_MISMATCH")
    if mode == "HARNESS" and (not harness_flag or ipc_mode != "AUTHENTICATED_HARNESS" or capability_mode != "HARNESS_SESSION"):
        raise SupervisorRejected("MODE_MISMATCH")
    if argv.count("--authenticated-worker") != 1:
        raise SupervisorRejected("MODE_MISMATCH")
    if request_deadline <= 0 or request_deadline > 5 or session_deadline <= 0 or session_deadline > 15:
        raise SupervisorRejected("DEADLINE_ABOVE_CAP")
    if step not in {"summary", "pricing"} or not isinstance(session_id, str) or not session_id.startswith("r56-") or len(session_id) != 36:
        raise SupervisorRejected("MODE_REJECTED")
    return {
        "dispatch": mode,
        "verification": "REAL_DISPATCH_CONTRACT_VERIFIED" if mode == "REAL" else "HARNESS_DISPATCH_CONTRACT",
        "network_execution": "REAL_NETWORK_EXECUTION_NOT_TESTED",
        "argv": argv,
        "ipc_mode": ipc_mode,
        "capability_mode": capability_mode,
        "authorisation_kind": capability_mode,
        "session_id": session_id,
        "step": step,
        "host": gate.LIVE_HOST,
        "port": gate.LIVE_PORT,
        "plan_id": gate.PLAN_ID,
        "request_budget": 2,
        "request_deadline_seconds": request_deadline,
        "session_deadline_seconds": session_deadline,
    }


def assert_dispatch_consistent(contract: dict[str, Any]) -> None:
    """Reject a mixture of the real worker and the harness IPC, or the reverse."""
    argv = contract.get("argv")
    if not isinstance(argv, list):
        raise SupervisorRejected("MODE_MISMATCH")
    real_ipc = contract.get("ipc_mode") == "REAL_SESSION"
    harness_flag = "--harness-transport" in argv
    real_capability = contract.get("capability_mode") == "REAL_SESSION"
    harness_capability = contract.get("capability_mode") == "HARNESS_SESSION"
    if real_ipc != real_capability or harness_flag == real_ipc or harness_capability == real_ipc:
        raise SupervisorRejected("MODE_MISMATCH")
    if contract.get("authorisation_kind") != contract.get("capability_mode"):
        raise SupervisorRejected("MODE_MISMATCH")


def redeem_for_dispatch(issuer: Any, capability: str, *, session_id: str, step: str, contract: dict[str, Any]) -> None:
    """Redeem with the mode on the parent contract. The child does not choose that mode."""
    assert_dispatch_consistent(contract)
    mode = contract.get("capability_mode")
    if mode not in {"HARNESS_SESSION", "REAL_SESSION"}:
        raise SupervisorRejected("MODE_REJECTED")
    if contract.get("dispatch") == "REAL" and mode != "REAL_SESSION":
        raise SupervisorRejected("MODE_MISMATCH")
    if contract.get("dispatch") == "HARNESS" and mode != "HARNESS_SESSION":
        raise SupervisorRejected("MODE_MISMATCH")
    if contract.get("session_id") != session_id or contract.get("step") != step:
        raise SupervisorRejected("MODE_MISMATCH")
    issuer.redeem(capability, session_id=session_id, step=step, mode=mode)


def _authorisation(session_id: str, step: str, capability: str, kind: str) -> dict[str, Any]:
    gate = _load(HERE, "r56p6", "live_session_gate")
    if kind not in {"HARNESS_SESSION", "REAL_SESSION"}:
        raise SupervisorRejected("MODE_REJECTED")
    return {
        "kind": kind,
        "session_id": session_id,
        "step": step,
        "host": gate.LIVE_HOST,
        "port": gate.LIVE_PORT,
        "plan_id": gate.PLAN_ID,
        "capability": capability,
    }


def _spawn_authenticated(
    *,
    step: str,
    prior: list[str],
    fixture: str,
    status: int,
    stall: str | None,
    ignore_seconds: float,
    request_deadline: float,
    session_deadline: float,
    session_started: float,
    session_id: str,
    collected_at: str,
    account_id: str,
    token: str,
    budget: SessionBudget,
    issuer: Any,
    capabilities: list[str],
    dispatch_mode: str,
    tracker: ChildTracker,
    interrupt_at: str | None = None,
    fault_at: str | None = None,
) -> tuple[dict[str, Any] | None, bool, bool, bool, bool]:
    global LAST_ARGV, LAST_IPC_WRITE_CLOSED, LAST_PROC, LAST_PUBLIC, LAST_CHILD_RESULTS
    if interrupt_at == "before_spawn":
        raise KeyboardInterrupt
    remaining = session_deadline - (time.monotonic() - session_started)
    if remaining <= 0:
        raise SupervisorRejected("SESSION_DEADLINE")
    budget.reserve()
    contract = dispatch_contract(
        dispatch_mode,
        session_id=session_id,
        step=step,
        request_deadline=request_deadline,
        session_deadline=session_deadline,
    )
    assert_dispatch_consistent(contract)
    gate = _load(HERE, "r56p6", "live_session_gate")
    if dispatch_mode == "REAL":
        gate.assert_real_session()
    public = {
        "schema": "r56.phase6.ipc.2",
        "mode": contract["ipc_mode"],
        "step": step,
        "prior": prior,
        "session_id": session_id,
        "collected_at": collected_at,
        "fixture": fixture,
    }
    LAST_PUBLIC.append(dict(public))
    ipc = _load(HERE, "r56p6", "credential_ipc")
    capability = issuer.issue(session_id=session_id, step=step, mode=contract["capability_mode"], lifetime=session_deadline)
    capabilities.append(capability)
    frame = ipc.authenticated_frame(
        public,
        account_id=account_id,
        token=token,
        authorisation=_authorisation(session_id, step, capability, contract["authorisation_kind"]),
        status=status,
        stall=stall,
        ignore_seconds=ignore_seconds if stall else None,
        ipc_mode=contract["ipc_mode"],
    )
    argv = list(contract["argv"])
    LAST_ARGV = argv
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=child_env(),
        cwd=str(HERE),
    )
    LAST_PROC = proc
    tracker.add(proc)
    assert proc.stdin is not None and proc.stdout is not None
    if fault_at == "after_spawn":
        raise RuntimeError("SESSION_FAILED")
    proc.stdin.write(frame + b"\n")
    proc.stdin.flush()
    del frame
    if fault_at == "ipc":
        raise RuntimeError("SESSION_FAILED")
    if interrupt_at == "handshake":
        raise KeyboardInterrupt
    if fault_at == "handshake":
        raise RuntimeError("SESSION_FAILED")
    timeout = min(request_deadline, remaining)
    holder: dict[str, bytes] = {}

    def _read_ready() -> None:
        holder["line"] = proc.stdout.readline()

    reader = threading.Thread(target=_read_ready, daemon=True)
    reader.start()
    reader.join(timeout)
    terminated = False
    if reader.is_alive():
        proc.kill()
        proc.stdin.close()
        proc.communicate()
        LAST_IPC_WRITE_CLOSED = True
        capability = ""
        return None, True, False, True, False
    ready_line = holder.get("line", b"")
    approved = False
    try:
        ready = json.loads(ready_line.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        ready = None
    if isinstance(ready, dict) and ready.get("ready") is True and ready.get("step") == step:
        expected = hashlib.sha256(capability.encode("utf-8")).hexdigest()
        presented = ready.get("capability_sha256")
        matched = isinstance(presented, str) and len(presented) == len(expected) and hmac.compare_digest(presented, expected)
        if matched:
            try:
                redeem_for_dispatch(issuer, capability, session_id=session_id, step=step, contract=contract)
            except (gate.GateRejected, SupervisorRejected):
                approved = False
            else:
                approved = True
        proc.stdin.write(b"CAP_OK\n" if approved else b"CAP_NO\n")
        proc.stdin.flush()
    proc.stdin.close()
    write_closed = False
    try:
        proc.stdin.write(b"x")
    except (ValueError, OSError):
        write_closed = True
    LAST_IPC_WRITE_CLOSED = write_closed
    if interrupt_at == "response":
        raise KeyboardInterrupt
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        terminated = True
        proc.kill()
        out, err = proc.communicate()
    del err
    if not isinstance(ready, dict) or ready.get("ready") is not True:
        out = ready_line + out
    alive = proc.poll() is None
    held_capability = capability
    capability = ""
    if terminated:
        return None, True, alive, write_closed, False
    text = out.decode("utf-8", errors="replace")
    exact = _exact_secrets(token) + (account_id, held_capability, "Bearer " + token, "Authorization: Bearer " + token)
    held_capability = ""
    if _sensitive(text, token, exact):
        blocked = _child_error("SENSITIVE_OUTPUT_BLOCKED", step)
        LAST_CHILD_RESULTS.append(blocked)
        return blocked, False, False, write_closed, False
    if not text.strip():
        code = "CHILD_CRASHED" if proc.returncode not in (0, None) else "MALFORMED_CHILD_RESULT"
        return _child_error(code, step), False, False, write_closed, False
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return _child_error("MALFORMED_CHILD_RESULT", step), False, False, write_closed, False
    if not isinstance(payload, dict) or payload.get("data_source") != _source_for(dispatch_mode):
        return _child_error("MALFORMED_CHILD_RESULT", step), False, False, write_closed, False
    if payload.get("step") != step or payload.get("executable_order") != "NOT_PRODUCED":
        return _child_error("MALFORMED_CHILD_RESULT", step), False, False, write_closed, False
    LAST_CHILD_RESULTS.append(payload)
    return payload, False, False, write_closed, payload.get("ipc_closed") is True


def run_authenticated_harness_session(
    *,
    answer: str,
    credential_source: Any,
    summary_fixture: str = "summary",
    pricing_fixture: str = "pricing",
    summary_status: int = 200,
    pricing_status: int = 200,
    stall: str | None = None,
    stall_step: str = "summary",
    ignore_seconds: float = 10.0,
    request_deadline: float = 5.0,
    session_deadline: float = 15.0,
    log_dir: Path | None = None,
    session_id: str | None = None,
    collected_at: str | None = None,
    live: bool = False,
) -> dict[str, Any]:
    """Harness parent. It always selects HARNESS and cannot launch the real worker."""
    gate = _load(HERE, "r56p6", "live_session_gate")
    if live:
        gate.assert_real_session()
    screen = gate.render_plan()
    confirmation = gate.confirm_one_session(answer, screen=screen)
    if confirmation.get("network_permitted") is not False or confirmation.get("real_session_source_enablement") is not False:
        raise SupervisorRejected("NETWORK_PERMITTED_REJECTED")
    try:
        gate.issue_runtime_authorisation()
    except gate.GateRejected as exc:
        if exc.code != "REAL_OANDA_SESSION_NOT_AUTHORISED":
            raise
    else:
        raise SupervisorRejected("REAL_GRANT_ISSUED")
    return _execute_authenticated_session(
        dispatch_mode="HARNESS",
        credential_source=credential_source,
        summary_fixture=summary_fixture,
        pricing_fixture=pricing_fixture,
        summary_status=summary_status,
        pricing_status=pricing_status,
        stall=stall,
        stall_step=stall_step,
        ignore_seconds=ignore_seconds,
        request_deadline=request_deadline,
        session_deadline=session_deadline,
        log_dir=log_dir,
        session_id=session_id,
        collected_at=collected_at,
    )


def _execute_authenticated_session(
    *,
    dispatch_mode: str,
    credential_source: Any,
    summary_fixture: str,
    pricing_fixture: str,
    summary_status: int,
    pricing_status: int,
    stall: str | None,
    stall_step: str,
    ignore_seconds: float,
    request_deadline: float,
    session_deadline: float,
    log_dir: Path | None,
    session_id: str | None,
    collected_at: str | None,
    interrupt_at: str | None = None,
    fault_at: str | None = None,
    authorisation: object = None,
) -> dict[str, Any]:
    """Shared parent loop. REAL is reachable only after the source switch; HARNESS cannot select it."""
    global LAST_PUBLIC, LAST_CHILD_RESULTS, LAST_ISSUER, LAST_PROC, LAST_TRACKER
    gate = _load(HERE, "r56p6", "live_session_gate")
    if dispatch_mode == "REAL":
        gate.assert_real_session()
    elif dispatch_mode != "HARNESS":
        raise SupervisorRejected("MODE_REJECTED")
    if request_deadline <= 0 or request_deadline > 5 or session_deadline <= 0 or session_deadline > 15:
        raise SupervisorRejected("DEADLINE_ABOVE_CAP")
    target = _log_dir(log_dir, dispatch_mode=dispatch_mode)
    account_id, token = credential_source()
    held_account, held_token = account_id, token
    transport = _load(HERE, "r56p6", "restricted_live_transport")
    transport.validate_authenticated_account(account_id)
    session = session_id or new_session_id()
    collected = collected_at or _now()
    budget = SessionBudget()
    LAST_PUBLIC = []
    LAST_CHILD_RESULTS = []
    issuer = gate.CapabilityIssuer()
    LAST_ISSUER = issuer
    LAST_PROC = None
    tracker = ChildTracker()
    LAST_TRACKER = tracker
    capabilities: list[str] = []
    wall_start = time.monotonic()
    summary_payload = None
    pricing_payload = None
    error = "NONE"
    terminated = False
    alive = False
    ipc_write_closed = False
    ipc_child_closed = False
    try:
        summary_payload, summary_term, summary_alive, write_closed, child_closed = _spawn_authenticated(
            step="summary",
            prior=[],
            fixture=summary_fixture,
            status=summary_status,
            stall=stall if stall_step == "summary" else None,
            ignore_seconds=ignore_seconds,
            request_deadline=request_deadline,
            session_deadline=session_deadline,
            session_started=wall_start,
            session_id=session,
            collected_at=collected,
            account_id=account_id,
            token=token,
            budget=budget,
            issuer=issuer,
            capabilities=capabilities,
            dispatch_mode=dispatch_mode,
            tracker=tracker,
            interrupt_at=interrupt_at if interrupt_at in {"before_spawn", "handshake", "response"} else None,
            fault_at=fault_at if fault_at in {"after_spawn", "handshake", "ipc"} else None,
        )
        terminated = summary_term
        alive = summary_alive
        ipc_write_closed = write_closed
        ipc_child_closed = child_closed
        if summary_term:
            error = "CHILD_TERMINATED"
        elif summary_payload is None:
            error = "CHILD_CRASHED"
        elif summary_payload.get("error_code") != "NONE":
            error = str(summary_payload["error_code"])
        elif not isinstance(summary_payload.get("diagnostics"), dict) or summary_payload["diagnostics"].get("outcome") != "DIAGNOSTIC_RECORDED":
            error = "SUMMARY_REJECTED"
        else:
            if interrupt_at == "between_steps":
                raise KeyboardInterrupt
            if fault_at == "between_steps":
                raise RuntimeError("SESSION_FAILED")
            pricing_payload, pricing_term, pricing_alive, write_closed, child_closed = _spawn_authenticated(
                step="pricing",
                prior=["summary"],
                fixture=pricing_fixture,
                status=pricing_status,
                stall=stall if stall_step == "pricing" else None,
                ignore_seconds=ignore_seconds,
                request_deadline=request_deadline,
                session_deadline=session_deadline,
                session_started=wall_start,
                session_id=session,
                collected_at=collected,
                account_id=account_id,
                token=token,
                budget=budget,
                issuer=issuer,
                capabilities=capabilities,
                dispatch_mode=dispatch_mode,
                tracker=tracker,
            )
            terminated = pricing_term
            alive = pricing_alive
            ipc_write_closed = write_closed
            ipc_child_closed = child_closed and ipc_child_closed
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
    except KeyboardInterrupt:
        error = "SESSION_INTERRUPTED"
        if tracker.procs:
            terminated = True
    except Exception:
        error = "SESSION_FAILED"
        if tracker.procs:
            terminated = True
    finally:
        cleanup_failed = False
        try:
            tracker.cleanup()
        except Exception:
            cleanup_failed = True
        try:
            issuer.expire_all()
        except Exception:
            cleanup_failed = True
        try:
            alive = any(proc.poll() is None for proc in tracker.procs)
        except Exception:
            cleanup_failed = True
            alive = True
        if cleanup_failed:
            alive = True
            if error == "NONE":
                error = "CHILD_CLEANUP_FAILED"
    session_authorised = (
        dispatch_mode == "REAL"
        and isinstance(authorisation, _VerifiedRealAuthorisation)
        and gate.REAL_SESSION_SOURCE_ENABLEMENT is True
    )
    attempted = session_authorised and budget.started > 0
    received = attempted and error == "NONE" and _broker_received(summary_payload) and _broker_received(pricing_payload)
    record = None
    path = None
    try:
        if fault_at == "write":
            raise RuntimeError("SESSION_FAILED")
        record = _record(
            collected,
            session,
            summary_payload,
            pricing_payload,
            error=error,
            terminated=terminated,
            alive=alive,
            children=budget.started,
            elapsed=time.monotonic() - wall_start,
            request_deadline=request_deadline,
            session_deadline=session_deadline,
            ipc_write_closed=ipc_write_closed,
            ipc_child_closed=ipc_child_closed,
            dispatch_mode=dispatch_mode,
            session_authorised=session_authorised,
            network_attempted=attempted,
            broker_response_received=received,
        )
        text = json.dumps(record, indent=2, sort_keys=True)
        exact = _exact_secrets(held_token) + (held_account, *capabilities, "Bearer " + held_token, "Authorization: Bearer " + held_token)
        if _sensitive(text, held_token, exact):
            record = _record(
                collected,
                session,
                None,
                None,
                error="SENSITIVE_OUTPUT_BLOCKED",
                terminated=terminated,
                alive=alive,
                children=budget.started,
                elapsed=time.monotonic() - wall_start,
                request_deadline=request_deadline,
                session_deadline=session_deadline,
                ipc_write_closed=ipc_write_closed,
                ipc_child_closed=False,
                dispatch_mode=dispatch_mode,
                session_authorised=session_authorised,
                network_attempted=attempted,
                broker_response_received=False,
            )
            text = json.dumps(record, indent=2, sort_keys=True)
        record["record_persisted"] = True
        text = json.dumps(record, indent=2, sort_keys=True)
        path = _allocate(target, session)
        _persist_record(path, text)
    except Exception:
        code = "SESSION_FAILED" if fault_at == "write" else "RECORD_PERSISTENCE_FAILED"
        try:
            if not isinstance(record, dict):
                record = _record(
                    collected,
                    session,
                    summary_payload,
                    pricing_payload,
                    error=code,
                    terminated=terminated,
                    alive=alive,
                    children=budget.started,
                    elapsed=time.monotonic() - wall_start,
                    request_deadline=request_deadline,
                    session_deadline=session_deadline,
                    ipc_write_closed=ipc_write_closed,
                    ipc_child_closed=ipc_child_closed,
                    dispatch_mode=dispatch_mode,
                    session_authorised=session_authorised,
                    network_attempted=attempted,
                    broker_response_received=received,
                )
            else:
                _mark_persistence_failed(record, code)
            text = json.dumps(record, indent=2, sort_keys=True)
            exact = _exact_secrets(held_token) + (held_account, *capabilities, "Bearer " + held_token, "Authorization: Bearer " + held_token)
            if _sensitive(text, held_token, exact):
                record = _record(
                    collected,
                    session,
                    None,
                    None,
                    error=code,
                    terminated=terminated,
                    alive=alive,
                    children=budget.started,
                    elapsed=time.monotonic() - wall_start,
                    request_deadline=request_deadline,
                    session_deadline=session_deadline,
                    ipc_write_closed=ipc_write_closed,
                    ipc_child_closed=False,
                    dispatch_mode=dispatch_mode,
                    session_authorised=session_authorised,
                    network_attempted=attempted,
                    broker_response_received=received,
                )
        except Exception:
            _drop_empty_record(path)
            raise SupervisorRejected(code) from None
        _drop_empty_record(path)
    held_account = ""
    held_token = ""
    capabilities.clear()
    return record


class _VerifiedRealAuthorisation:
    """Exists only after the source switch has already passed. Tests cannot mint one while it is off."""

    def __init__(self) -> None:
        _load(HERE, "r56p6", "live_session_gate").assert_real_session()


def run_real_session(
    *,
    answer: str | None = None,
    confirmation: dict[str, object] | None = None,
    reader: Any = None,
    now: float | None = None,
    summary_fixture: str = "summary",
    pricing_fixture: str = "pricing",
    summary_status: int = 200,
    pricing_status: int = 200,
    stall: str | None = None,
    stall_step: str = "summary",
    ignore_seconds: float = 10.0,
    request_deadline: float = 5.0,
    session_deadline: float = 15.0,
    log_dir: Path | None = None,
    session_id: str | None = None,
    collected_at: str | None = None,
) -> dict[str, Any]:
    """Future real dispatch. The source switch refuses before the plan, prompts, or a worker."""
    gate = _load(HERE, "r56p6", "live_session_gate")
    gate.assert_real_session()
    screen = gate.render_plan()
    if confirmation is None:
        if answer is None:
            if reader is None:
                raise gate.GateRejected("CONFIRMATION_REJECTED")
            answer = reader(screen)
        if not isinstance(answer, str) or not answer.strip():
            raise gate.GateRejected("CONFIRMATION_REJECTED")
        confirmation = gate.confirm_one_session(answer, screen=screen)
    gate.accept_confirmation(confirmation, now=now)
    activation = _load(HERE, "r56p6", "one_session_activation")
    try:
        activation.consume()
    except activation.ActivationRejected as exc:
        raise gate.GateRejected(exc.code) from None
    fresh_session = session_id or new_session_id()
    ipc = _load(HERE, "r56p6", "credential_ipc")
    parent_grant = gate.issue_runtime_authorisation(
        answer=gate.ONE_SESSION_PHRASE,
        confirmation=confirmation,
        plan=gate.fixed_plan(),
        session_id=fresh_session,
        step="summary",
    )
    prompted_account = ipc.prompt_account_id(grant=parent_grant, session_id=fresh_session, step="summary")
    prompted_token = ipc.prompt_hidden_token(grant=parent_grant, session_id=fresh_session, step="summary")
    gate.expire_grant(parent_grant)

    def credential_source() -> tuple[str, str]:
        return prompted_account, prompted_token

    return _execute_authenticated_session(
        dispatch_mode="REAL",
        credential_source=credential_source,
        summary_fixture=summary_fixture,
        pricing_fixture=pricing_fixture,
        summary_status=summary_status,
        pricing_status=pricing_status,
        stall=stall,
        stall_step=stall_step,
        ignore_seconds=ignore_seconds,
        request_deadline=request_deadline,
        session_deadline=session_deadline,
        log_dir=log_dir,
        session_id=fresh_session,
        collected_at=collected_at,
        authorisation=_VerifiedRealAuthorisation(),
    )

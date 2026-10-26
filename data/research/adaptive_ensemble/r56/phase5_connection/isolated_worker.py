"""One sealed child step. The child returns reduced diagnostics and cannot open a live socket."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PHASE2 = HERE.parent / "phase2_offline"
PHASE3 = HERE.parent / "phase3_offline"
SCHEMA = "r56.phase5.child.1"
SUMMARY_PATTERN = "/v3/accounts/{accountID}/summary"
PRICING_PATTERN = "/v3/accounts/{accountID}/pricing"


def seal_network() -> None:
    """Block sockets after the standard library has built its TLS types.

    Replacing socket.socket before ssl is imported breaks that import. The
    replacements below still reject new sockets, name lookup, and HTTP clients.
    """
    import http.client
    import socket
    import ssl

    def blocked(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("NETWORK_SEALED")

    socket.socket = blocked  # type: ignore[misc, assignment]
    socket.create_connection = blocked  # type: ignore[assignment]
    socket.getaddrinfo = blocked  # type: ignore[assignment]
    ssl.SSLSocket = blocked  # type: ignore[misc, assignment]
    ssl.SSLContext.wrap_socket = blocked  # type: ignore[method-assign]
    http.client.HTTPConnection = blocked  # type: ignore[misc, assignment]
    http.client.HTTPSConnection = blocked  # type: ignore[misc, assignment]


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


def _fail(code: str, step: str = "none") -> dict[str, Any]:
    endpoint = ""
    if step == "summary":
        endpoint = SUMMARY_PATTERN
    elif step == "pricing":
        endpoint = PRICING_PATTERN
    return {
        "schema_version": SCHEMA,
        "data_source": "SYNTHETIC_TEST_ONLY",
        "step": step,
        "result": "REJECTED" if step in {"summary", "pricing"} else "NOT_SENT",
        "endpoint": endpoint,
        "diagnostics": "NOT_PRODUCED",
        "error_code": code,
        "validation_warnings": [],
        "missing_evidence": [],
        "executable_order": "NOT_PRODUCED",
    }


def run_job(job: dict[str, Any], *, child_process: bool = False) -> dict[str, Any]:
    seal_network()
    if not isinstance(job, dict):
        return _fail("JOB_REJECTED")
    if job.get("mode") != "OFFLINE_TEST" or job.get("connector") != "scripted":
        return _fail("LIVE_NETWORK_NOT_AUTHORISED")
    if job.get("network_permitted") is not False or job.get("confirmed") is not True:
        return _fail("CONFIRMATION_REQUIRED")
    if job.get("credential_classification") != "SYNTHETIC_TEST_ONLY" or job.get("authorization_present") is not True:
        return _fail("REAL_CREDENTIAL_USE_NOT_AUTHORISED")
    if any(key in job for key in ("token", "authorization", "account_id", "accountID", "Authorization")):
        return _fail("JOB_SECRET_REJECTED")
    stall = job.get("stall")
    if stall in {"hang", "ignore", "crash"} and not child_process:
        return _fail("STALL_REQUIRES_CHILD")
    if stall == "hang":
        time.sleep(30)
    elif stall == "ignore":
        time.sleep(float(job.get("ignore_seconds") or 10))
    elif stall == "crash":
        os._exit(3)
    elif stall == "dns":
        import socket

        try:
            socket.getaddrinfo("api-fxtrade.oanda.com", 443)
        except RuntimeError:
            return _fail("NETWORK_SEALED")
        return _fail("NETWORK_SEAL_FAILED")
    step = job.get("step")
    if step not in {"summary", "pricing"}:
        return _fail("STEP_REJECTED")
    session_id = job.get("session_id")
    collected = job.get("collected_at")
    if not isinstance(session_id, str) or not session_id.startswith("r56-") or len(session_id) != 36:
        return _fail("SESSION_ID_REJECTED", step)
    if not isinstance(collected, str) or len(collected) > 40:
        return _fail("COLLECTED_AT_REJECTED", step)
    try:
        if stall == "raise":
            transport = _load(HERE, "r56p5", "restricted_https_transport")
            raise RuntimeError(transport.SYNTHETIC_ACCOUNT_ID)
        return _step(job, step, session_id, collected)
    except Exception:
        failed = _fail("EXCEPTION_CONTAINED", step)
        failed["validation_warnings"] = ["exception_contained"]
        return failed


def _step(job: dict[str, Any], step: str, session_id: str, collected: str) -> dict[str, Any]:
    transport_mod = _load(HERE, "r56p5", "restricted_https_transport")
    fixtures = _load(HERE, "r56p5", "synthetic_fixtures")
    plan = _load(PHASE3, "r56p3", "readonly_request_plan")
    gate = _load(PHASE3, "r56p3", "readonly_request_gate")
    body_text = job.get("body_text")
    body = body_text.encode("utf-8") if isinstance(body_text, str) else None
    connector = fixtures.ScriptedConnector(
        job.get("document") if isinstance(job.get("document"), dict) else {},
        status_code=int(job.get("status") or 200),
        body=body,
        fill=int(job.get("fill") or 0),
        tls_policy=job.get("tls_policy") if isinstance(job.get("tls_policy"), dict) else None,
        proxy_from_environment=job.get("proxy_from_environment") is True,
    )
    transport = transport_mod.RestrictedTransport(connector, request_deadline=float(job.get("request_deadline") or 5.0))
    try:
        if step == "summary":
            gate.approve(plan.summary_candidate(), step=1, prior=[])
            if job.get("prior") not in ([], None):
                return _fail("SEQUENCE_REJECTED", step)
            raw = transport.get_account_summary(transport_mod.SYNTHETIC_ACCOUNT_ID, authorization_present=True)
        else:
            gate.approve(plan.pricing_candidate(), step=2, prior=["summary"])
            if job.get("prior") != ["summary"]:
                return _fail("SEQUENCE_REJECTED", step)
            raw = transport.get_pricing(
                transport_mod.SYNTHETIC_ACCOUNT_ID,
                authorization_present=True,
                prior=("summary",),
            )
    except gate.GateRejected as exc:
        return _fail(exc.code, step)
    except transport_mod.TransportRejected as exc:
        return _fail(exc.code, step)
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return _fail("MALFORMED_JSON", step)
    stamped = _stamp(step, document, session_id, collected)
    if isinstance(stamped, dict) and stamped.get("outcome") != "DIAGNOSTIC_RECORDED":
        failed = _fail("SUMMARY_REJECTED" if step == "summary" else "PRICING_REJECTED", step)
        failed["diagnostics"] = stamped
        failed["validation_warnings"] = list(stamped.get("validation_warnings") or [])
        return failed
    if isinstance(stamped, list) and (not stamped or any(item.get("outcome") != "DIAGNOSTIC_RECORDED" for item in stamped)):
        failed = _fail("PRICING_REJECTED", step)
        failed["diagnostics"] = stamped
        return failed
    warnings: list[str] = []
    missing: list[str] = []
    if isinstance(stamped, dict):
        warnings.extend(stamped.get("validation_warnings") or [])
        missing.extend(stamped.get("missing_evidence") or [])
    else:
        for item in stamped:
            warnings.extend(item.get("validation_warnings") or [])
            missing.extend(item.get("missing_evidence") or [])
    return {
        "schema_version": SCHEMA,
        "data_source": "SYNTHETIC_TEST_ONLY",
        "step": step,
        "result": "SYNTHETIC_RESPONSE_ACCEPTED",
        "endpoint": transport_mod.SUMMARY_PATTERN if step == "summary" else transport_mod.PRICING_PATTERN,
        "diagnostics": stamped,
        "error_code": "NONE",
        "validation_warnings": _unique(warnings),
        "missing_evidence": _unique(missing),
        "executable_order": "NOT_PRODUCED",
    }


def _stamp(step: str, document: Any, session_id: str, collected: str) -> Any:
    writer = _load(PHASE2, "r56p2", "diagnostic_writer")
    if step == "summary":
        account_mod = _load(PHASE2, "r56p2", "account_diagnostics")
        body, _secrets = account_mod.build(json.loads(json.dumps(document)))
        return writer.stamp(body, data_source="SYNTHETIC_TEST_ONLY", session_id=session_id, collected_at=collected)
    pricing_mod = _load(PHASE2, "r56p2", "pricing_diagnostics")
    bodies, _secrets = pricing_mod.build(json.loads(json.dumps(document)))
    return [
        writer.stamp(body, data_source="SYNTHETIC_TEST_ONLY", session_id=session_id, collected_at=collected)
        for body in bodies
    ]


def _unique(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload))


def main(argv: list[str]) -> int:
    if argv != ["--offline-worker"]:
        return 2
    try:
        raw = sys.stdin.buffer.read(300_000)
        if len(raw) >= 300_000:
            _emit(_fail("JOB_TOO_LARGE"))
            return 2
        job = json.loads(raw.decode("utf-8"))
    except Exception:
        _emit(_fail("JOB_REJECTED"))
        return 2
    if not isinstance(job, dict):
        _emit(_fail("JOB_REJECTED"))
        return 2
    if job.get("stall") == "malformed":
        sys.stdout.write("{")
        return 0
    if job.get("stall") == "leak":
        transport = _load(HERE, "r56p5", "restricted_https_transport")
        sys.stderr.write(transport.SYNTHETIC_ACCOUNT_ID)
        sys.stdout.write(json.dumps({"token": "SYNTHETIC-NOT-REAL", "account_id": transport.SYNTHETIC_ACCOUNT_ID}))
        return 0
    try:
        result = run_job(job, child_process=True)
    except Exception:
        result = _fail("EXCEPTION_CONTAINED")
    _emit(result)
    return 0 if result.get("error_code") == "NONE" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

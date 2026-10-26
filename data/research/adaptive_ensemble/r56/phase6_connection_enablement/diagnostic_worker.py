"""One supervised request. The child returns reduced diagnostics and closes its IPC pipe."""

from __future__ import annotations

import hashlib
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
PHASE5 = HERE.parent / "phase5_connection"
SCHEMA = "r56.phase6.child.1"
SUMMARY_PATTERN = "/v3/accounts/{accountID}/summary"
PRICING_PATTERN = "/v3/accounts/{accountID}/pricing"
NETWORK_SEALED = False
LAST_EXCHANGE: Any = None


def seal_network() -> None:
    """Offline seal. Authenticated harness mode must not call this."""
    global NETWORK_SEALED
    import http.client
    import socket
    import ssl

    NETWORK_SEALED = True

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


def result_labels(*, real: bool, received: bool, step: str, attempted: bool = True) -> dict[str, str]:
    """Label a step from what happened. A failed or unattempted step is not a received response."""
    if received:
        outcome = "BROKER_RESPONSE_RECEIVED" if real else "SYNTHETIC_RESPONSE_ACCEPTED"
        network = "REAL_NETWORK_COMPLETED" if real else "NOT_AUTHORISED"
    elif not attempted or step not in {"summary", "pricing"}:
        outcome = "NOT_SENT"
        network = "REAL_NETWORK_NOT_COMPLETED" if real else "NOT_AUTHORISED"
    else:
        outcome = "REJECTED"
        network = "REAL_NETWORK_NOT_COMPLETED" if real else "NOT_AUTHORISED"
    if real:
        return {
            "data_source": "REAL_OANDA_LIVE_DIAGNOSTIC",
            "result": outcome,
            "network_status": network,
            "confirmation": "OPERATOR_CONFIRMED_READ_ONLY",
        }
    return {
        "data_source": "SYNTHETIC_TEST_ONLY",
        "result": outcome,
        "network_status": network,
        "confirmation": "CONFIRMED_SYNTHETIC",
    }


def _fail(code: str, step: str = "none", *, real: bool = False) -> dict[str, Any]:
    endpoint = SUMMARY_PATTERN if step == "summary" else PRICING_PATTERN if step == "pricing" else ""
    labels = result_labels(real=real, received=False, step=step, attempted=step in {"summary", "pricing"})
    return {
        "schema_version": SCHEMA,
        "data_source": labels["data_source"],
        "step": step,
        "result": labels["result"],
        "endpoint": endpoint,
        "diagnostics": "NOT_PRODUCED",
        "error_code": code,
        "validation_warnings": [],
        "missing_evidence": [],
        "executable_order": "NOT_PRODUCED",
        "ipc_closed": True,
        "authorization_accepted": False,
        "network_status": labels["network_status"],
        "confirmation": labels["confirmation"],
    }


def run_job(
    job: dict[str, Any],
    header: str,
    *,
    child_process: bool,
    ipc_closed: bool,
    mode: str = "OFFLINE",
) -> dict[str, Any]:
    if mode == "OFFLINE":
        seal_network()
    elif mode != "AUTHENTICATED_HARNESS":
        return _fail("REAL_OANDA_SESSION_NOT_AUTHORISED")
    stall = job.get("stall")
    step = job.get("step")
    if stall == "dns":
        import socket

        try:
            socket.getaddrinfo("api-fxtrade.oanda.com", 443)
        except RuntimeError:
            return _fail("NETWORK_SEALED", step if step in {"summary", "pricing"} else "none")
        return _fail("NETWORK_SEAL_FAILED", step if step in {"summary", "pricing"} else "none")
    if step not in {"summary", "pricing"}:
        return _fail("STEP_REJECTED")
    if stall in {"hang", "ignore", "crash"} and not child_process:
        return _fail("STALL_REQUIRES_CHILD", step)
    if stall == "hang":
        time.sleep(30)
    elif stall == "ignore":
        time.sleep(float(job.get("ignore_seconds") or 10))
    elif stall == "crash":
        os._exit(3)
    try:
        if stall == "raise":
            raise RuntimeError(header)
        result = _step(job, step, header, mode=mode)
    except Exception:
        result = _fail("EXCEPTION_CONTAINED", step)
        result["validation_warnings"] = ["exception_contained"]
    finally:
        header = ""
    result["ipc_closed"] = ipc_closed
    return result


def select_exchange(mode: str, job: dict[str, Any], connection: Any = None) -> Any:
    """Offline mode returns FakeExchange. The harness returns LiveExchange around an injected connection."""
    global LAST_EXCHANGE
    transport_mod = _load(HERE, "r56p6", "restricted_live_transport")
    if mode == "OFFLINE":
        document = _fixture(job, str(job.get("step") or "summary"))
        body_text = job.get("body_text")
        body = body_text.encode("utf-8") if isinstance(body_text, str) else None
        exchange = transport_mod.FakeExchange(
            document,
            status_code=int(job.get("status") or 200),
            body=body,
            fill=int(job.get("fill") or 0),
            tls_policy=job.get("tls_policy") if isinstance(job.get("tls_policy"), dict) else None,
            proxy_from_environment=job.get("proxy_from_environment") is True,
        )
    elif mode == "AUTHENTICATED_HARNESS":
        if connection is None or connection.__class__ is not transport_mod.HarnessConnection:
            raise transport_mod.TransportRejected("REAL_OANDA_SESSION_NOT_AUTHORISED")
        exchange = transport_mod.LiveExchange(connection=connection)
    else:
        raise transport_mod.TransportRejected("REAL_OANDA_SESSION_NOT_AUTHORISED")
    LAST_EXCHANGE = exchange
    return exchange


def _step(
    job: dict[str, Any],
    step: str,
    header: str,
    *,
    exchange: Any = None,
    selector: str | None = None,
    mode: str = "OFFLINE",
    grant: object = None,
    real: bool = False,
) -> dict[str, Any]:
    transport_mod = _load(HERE, "r56p6", "restricted_live_transport")
    plan = _load(PHASE3, "r56p3", "readonly_request_plan")
    gate = _load(PHASE3, "r56p3", "readonly_request_gate")
    session_id = job.get("session_id")
    collected = job.get("collected_at")
    if not isinstance(session_id, str) or not session_id.startswith("r56-") or len(session_id) != 36:
        return _fail("SESSION_ID_REJECTED", step, real=real)
    if not isinstance(collected, str) or len(collected) > 40:
        return _fail("COLLECTED_AT_REJECTED", step, real=real)
    if exchange is None:
        exchange = select_exchange("OFFLINE", job)
        selector = transport_mod.SELECTOR
        request_mode = "OFFLINE"
    else:
        request_mode = "AUTHENTICATED" if mode == "AUTHENTICATED" else "OFFLINE"
        if selector is None:
            selector = transport_mod.SELECTOR
    transport = transport_mod.RestrictedLiveTransport(
        exchange,
        grant=grant,
        session_id=session_id if request_mode == "AUTHENTICATED" else "",
    )
    try:
        if step == "summary":
            if request_mode == "OFFLINE":
                gate.approve(plan.summary_candidate(), step=1, prior=[])
            if job.get("prior") not in ([], None):
                return _fail("SEQUENCE_REJECTED", step, real=real)
            raw = transport.get_account_summary(selector, authorization_header=header, mode=request_mode)
        else:
            if request_mode == "OFFLINE":
                gate.approve(plan.pricing_candidate(), step=2, prior=["summary"])
            if job.get("prior") != ["summary"]:
                return _fail("SEQUENCE_REJECTED", step, real=real)
            raw = transport.get_pricing(selector, authorization_header=header, prior=("summary",), mode=request_mode)
    except gate.GateRejected as exc:
        return _fail(exc.code, step, real=real)
    except transport_mod.TransportRejected as exc:
        failed = _fail(exc.code, step, real=real)
        failed["authorization_accepted"] = exchange.authorization_accepted
        return failed
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return _fail("MALFORMED_JSON", step, real=real)
    stamped = _reduce(step, parsed, session_id, collected, real=real)
    if isinstance(stamped, dict) and stamped.get("outcome") != "DIAGNOSTIC_RECORDED":
        failed = _fail("SUMMARY_REJECTED", step, real=real)
        failed["diagnostics"] = stamped
        return failed
    if isinstance(stamped, list) and (not stamped or any(item.get("outcome") != "DIAGNOSTIC_RECORDED" for item in stamped)):
        failed = _fail("PRICING_REJECTED", step, real=real)
        failed["diagnostics"] = stamped
        return failed
    warnings: list[str] = []
    missing: list[str] = []
    rows = [stamped] if isinstance(stamped, dict) else stamped
    for item in rows:
        warnings.extend(item.get("validation_warnings") or [])
        missing.extend(item.get("missing_evidence") or [])
    labels = result_labels(real=real, received=True, step=step)
    return {
        "schema_version": SCHEMA,
        "data_source": labels["data_source"],
        "step": step,
        "result": labels["result"],
        "endpoint": SUMMARY_PATTERN if step == "summary" else PRICING_PATTERN,
        "diagnostics": stamped,
        "error_code": "NONE",
        "validation_warnings": _unique(warnings),
        "missing_evidence": _unique(missing),
        "executable_order": "NOT_PRODUCED",
        "ipc_closed": True,
        "authorization_accepted": exchange.authorization_accepted,
        "network_status": labels["network_status"],
        "confirmation": labels["confirmation"],
    }


def _fixture(job: dict[str, Any], step: str) -> dict[str, Any]:
    fixtures = _load(PHASE5, "r56p5fix", "synthetic_fixtures")
    name = job.get("fixture")
    if step == "summary":
        if name not in {None, "summary", "summary_no_currency"}:
            raise ValueError("fixture")
        return fixtures.summary_document(include_currency=name != "summary_no_currency")
    if name not in {None, "pricing", "pricing_no_bid"}:
        raise ValueError("fixture")
    bid = job.get("pricing_bid")
    return fixtures.pricing_document(include_bid=name != "pricing_no_bid", bid=bid if isinstance(bid, str) else "1.10000")


def _stamp(step: str, document: Any, session_id: str, collected: str) -> Any:
    writer = _load(PHASE2, "r56p2", "diagnostic_writer")
    if step == "summary":
        account_mod = _load(PHASE2, "r56p2", "account_diagnostics")
        body, _secrets = account_mod.build(json.loads(json.dumps(document)))
        return writer.stamp(body, data_source="SYNTHETIC_TEST_ONLY", session_id=session_id, collected_at=collected)
    pricing_mod = _load(PHASE2, "r56p2", "pricing_diagnostics")
    bodies, _secrets = pricing_mod.build(json.loads(json.dumps(document)))
    return [writer.stamp(body, data_source="SYNTHETIC_TEST_ONLY", session_id=session_id, collected_at=collected) for body in bodies]


def _reduce(step: str, document: Any, session_id: str, collected: str, *, real: bool) -> Any:
    """Harness results keep the Phase 2 synthetic stamp. Real results keep the Phase 2 field reduction only."""
    if not real:
        return _stamp(step, document, session_id, collected)
    copied = json.loads(json.dumps(document))
    if step == "summary":
        body, _secrets = _load(PHASE2, "r56p2", "account_diagnostics").build(copied)
        return body
    bodies, _secrets = _load(PHASE2, "r56p2", "pricing_diagnostics").build(copied)
    return bodies


def _unique(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


def _output_secrets(header: str, account_id: str | None = None) -> tuple[str, ...]:
    values: list[str] = []
    if isinstance(header, str) and header:
        values.append(header)
        if header.startswith("Bearer "):
            values.append(header[7:])
            values.append("Authorization: " + header)
    if isinstance(account_id, str) and account_id:
        values.append(account_id)
    pin = getattr(_load(PHASE5, "r56p5", "restricted_https_transport"), "SYNTHETIC_ACCOUNT_ID", "")
    if isinstance(pin, str) and pin:
        values.append(pin)
    return tuple(values)


def protect_output(payload: dict[str, Any], secrets: tuple[str, ...], step: str) -> str:
    """Block the payload when an exact secret would otherwise be written."""
    ipc = _load(HERE, "r56p6", "credential_ipc")
    text = json.dumps(payload)
    if not ipc.contains_exact(text, secrets):
        return text
    blocked = json.dumps(_fail("SENSITIVE_OUTPUT_BLOCKED", step if step in {"summary", "pricing"} else "summary"))
    scrubbed = ipc.redact_exact(blocked, secrets)
    if ipc.contains_exact(scrubbed, secrets):
        return json.dumps(_fail("SENSITIVE_OUTPUT_BLOCKED", "summary"))
    return scrubbed


def _emit(payload: dict[str, Any], secrets: tuple[str, ...] = (), step: str = "summary") -> None:
    sys.stdout.write(protect_output(payload, secrets, step))


def _capability_shape(token: object) -> bool:
    if not isinstance(token, str) or len(token) != 129 or token[64] != ".":
        return False
    return all(character in "0123456789abcdef" for character in token[:64] + token[65:])


def _annotate_exchange(result: dict[str, Any], exchange: Any) -> dict[str, Any]:
    connection = getattr(exchange, "connection", None)
    calls = getattr(connection, "calls", None)
    if calls:
        path = calls[-1][1]
        query = calls[-1][2]
        result["request_sha256"] = hashlib.sha256(path.encode("utf-8")).hexdigest()
        result["query_sha256"] = hashlib.sha256(json.dumps(query, sort_keys=True).encode("utf-8")).hexdigest()
    result["grant_checked"] = True
    result["real_connections_opened"] = 0
    result["exchange"] = "LiveExchange"
    return result


def run_authenticated_harness(raw: bytes, connection: Any, grant: object = None) -> dict[str, Any]:
    """Exercise LiveExchange with a parent-supplied grant. This process does not mint one."""
    if NETWORK_SEALED:
        return _fail("NETWORK_SEAL_UNEXPECTED")
    ipc = _load(HERE, "r56p6", "credential_ipc")
    transport_mod = _load(HERE, "r56p6", "restricted_live_transport")
    try:
        public, header, account_id = ipc.consume_authenticated(raw)
    except ipc.IpcRejected as exc:
        return _fail(exc.code)
    secrets = _output_secrets(header, account_id)
    step = str(public.get("step") or "summary")
    exchange = None
    try:
        if connection is None or connection.__class__ is not transport_mod.HarnessConnection:
            result = _fail("REAL_OANDA_SESSION_NOT_AUTHORISED", step)
        elif grant is None:
            result = _fail("GRANT_REJECTED", step)
        else:
            exchange = select_exchange("AUTHENTICATED_HARNESS", public, connection=connection)
            result = _step(
                public,
                step,
                header,
                exchange=exchange,
                selector=account_id,
                mode="AUTHENTICATED",
                grant=grant,
            )
            result = _annotate_exchange(result, exchange)
            _load(HERE, "r56p6", "live_session_gate").expire_grant(grant)
    except Exception:
        result = _fail("EXCEPTION_CONTAINED", step if step in {"summary", "pricing"} else "summary")
    finally:
        header = ""
    return json.loads(protect_output(result, secrets, step))


def run_authenticated_pair(
    summary_raw: bytes,
    pricing_raw: bytes,
    summary_connection: Any,
    pricing_connection: Any,
    summary_grant: object = None,
    pricing_grant: object = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Summary must succeed before pricing. A failed summary does not touch the pricing connection."""
    summary = run_authenticated_harness(summary_raw, summary_connection, grant=summary_grant)
    if summary.get("error_code") != "NONE":
        return summary, None
    return summary, run_authenticated_harness(pricing_raw, pricing_connection, grant=pricing_grant)


def _tripwire_https() -> None:
    """Fail closed if the harness process constructs a real connection. This is not an OS sandbox."""
    import http.client

    def blocked(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("HARNESS_NETWORK_FORBIDDEN")

    http.client.HTTPSConnection = blocked  # type: ignore[misc, assignment]
    http.client.HTTPConnection = blocked  # type: ignore[misc, assignment]


def _authenticated_child(*, harness: bool) -> int:
    gate = _load(HERE, "r56p6", "live_session_gate")
    if not harness:
        try:
            gate.assert_real_session()
        except gate.GateRejected as exc:
            _emit(_fail(exc.code))
            return 2
    else:
        _tripwire_https()
    real_labels = not harness
    ipc = _load(HERE, "r56p6", "credential_ipc")
    transport_mod = _load(HERE, "r56p6", "restricted_live_transport")
    try:
        raw = sys.stdin.buffer.readline(ipc.MAX_FRAME + 2)
        if len(raw) > ipc.MAX_FRAME + 1:
            raise ipc.IpcRejected("IPC_TOO_LARGE")
        if harness:
            public, header, account_id = ipc.consume_authenticated(raw)
        else:
            public, header, account_id = ipc.consume_real(raw)
    except Exception:
        code = "IPC_REJECTED"
        err = sys.exc_info()[1]
        if isinstance(err, ipc.IpcRejected):
            code = err.code
        elif isinstance(err, gate.GateRejected):
            code = err.code
        _emit(_fail(code, real=real_labels))
        return 1
    secrets = _output_secrets(header, account_id)
    step = public.get("step") if public.get("step") in {"summary", "pricing"} else "summary"
    presented = ""
    try:
        authorisation = public.get("authorisation")
        presented = authorisation.get("capability") if isinstance(authorisation, dict) else ""
        secrets = secrets + ((presented,) if isinstance(presented, str) and presented else ())
        if not isinstance(authorisation, dict) or not _capability_shape(presented):
            result = _fail("GRANT_REJECTED", step, real=real_labels)
        elif authorisation.get("session_id") != public.get("session_id") or authorisation.get("step") != step:
            result = _fail("CAPABILITY_REJECTED", step, real=real_labels)
        elif harness and authorisation.get("kind") != "HARNESS_SESSION":
            result = _fail("GRANT_REJECTED", step, real=real_labels)
        elif not harness and authorisation.get("kind") != "REAL_SESSION":
            result = _fail("GRANT_REJECTED", step, real=real_labels)
        else:
            digest = hashlib.sha256(presented.encode("utf-8")).hexdigest()
            sys.stdout.write(json.dumps({"ready": True, "step": step, "capability_sha256": digest}) + "\n")
            sys.stdout.flush()
            ack = sys.stdin.buffer.readline(32).strip()
            if ack != b"CAP_OK":
                result = _fail("CAPABILITY_REJECTED", step, real=real_labels)
            elif public.get("stall") == "hang":
                time.sleep(30)
                result = _fail("CHILD_STALLED", step, real=real_labels)
            elif public.get("stall") == "ignore":
                time.sleep(float(public.get("ignore_seconds") or 10))
                result = _fail("CHILD_STALLED", step, real=real_labels)
            elif public.get("stall") == "crash":
                os._exit(3)
            elif harness:
                document = _fixture(public, step)
                body_text = public.get("body_text")
                connection = transport_mod.HarnessConnection(
                    document,
                    status_code=int(public.get("status") or 200),
                    body=body_text.encode("utf-8") if isinstance(body_text, str) else None,
                    fill=int(public.get("fill") or 0),
                )
                grant = gate.bind_harness_grant(public.get("session_id"), step)
                exchange = select_exchange("AUTHENTICATED_HARNESS", public, connection=connection)
                result = _step(public, step, header, exchange=exchange, selector=account_id, mode="AUTHENTICATED", grant=grant)
                result = _annotate_exchange(result, exchange)
                sys.stdin.close()
                result["ipc_closed"] = sys.stdin.closed
                gate.expire_grant(grant)
            else:
                grant = gate.note_parent_ack("CAP_OK", public.get("session_id"), step)
                exchange = transport_mod.LiveExchange()
                result = _step(public, step, header, exchange=exchange, selector=account_id, mode="AUTHENTICATED", grant=grant, real=True)
                sys.stdin.close()
                gate.expire_grant(grant)
    except Exception:
        result = _fail("EXCEPTION_CONTAINED", step if step in {"summary", "pricing"} else "summary", real=real_labels)
    finally:
        header = ""
        presented = ""
    _emit(result, secrets, step if step in {"summary", "pricing"} else "summary")
    return 0 if result.get("error_code") == "NONE" else 1


def main(argv: list[str]) -> int:
    if argv == ["--authenticated-worker"]:
        return _authenticated_child(harness=False)
    if argv == ["--authenticated-worker", "--harness-transport"]:
        return _authenticated_child(harness=True)
    if argv != ["--offline-worker"]:
        return 2
    seal_network()
    ipc = _load(HERE, "r56p6", "credential_ipc")
    try:
        raw = sys.stdin.buffer.read(ipc.MAX_FRAME + 1)
        sys.stdin.close()
        public, header = ipc.consume(raw)
    except Exception:
        code = "IPC_REJECTED"
        err = sys.exc_info()[1]
        if isinstance(err, ipc.IpcRejected):
            code = err.code
        _emit(_fail(code))
        return 1
    secrets = _output_secrets(header)
    step = public.get("step") if public.get("step") in {"summary", "pricing"} else "summary"
    if public.get("stall") == "malformed":
        sys.stdout.write("{")
        return 0
    if public.get("stall") == "leak":
        pins = _load(PHASE5, "r56p5", "restricted_https_transport")
        sys.stderr.write(str(pins.SYNTHETIC_ACCOUNT_ID))
        sys.stderr.write(header)
        leaked = {"account_id": pins.SYNTHETIC_ACCOUNT_ID, "authorization": header}
        _emit(leaked, secrets, step)
        return 0
    try:
        result = run_job(public, header, child_process=True, ipc_closed=sys.stdin.closed)
    except Exception:
        result = _fail("EXCEPTION_CONTAINED")
    finally:
        header = ""
    _emit(result, secrets, str(result.get("step") or step))
    return 0 if result.get("error_code") == "NONE" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

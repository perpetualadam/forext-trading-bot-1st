"""Child for one instrument-metadata GET. It cannot mint its own capability."""

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


def _load(stem: str) -> Any:
    name = f"r61_{stem}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, HERE / f"{stem}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _tripwire_https() -> None:
    import http.client

    def blocked(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("HARNESS_NETWORK_FORBIDDEN")

    http.client.HTTPSConnection = blocked  # type: ignore[misc, assignment]
    http.client.HTTPConnection = blocked  # type: ignore[misc, assignment]


def _fail(code: str, *, real: bool) -> dict[str, Any]:
    return {
        "data_source": "REAL_OANDA_LIVE_INSTRUMENT_METADATA" if real else "HARNESS_INSTRUMENT_METADATA",
        "step": "instruments",
        "error_code": code,
        "executable_order": "NOT_PRODUCED",
        "order_payload": "NOT_PRODUCED",
        "spread_betting_classification": "NOT_VERIFIED",
        "stake_to_unit_mapping": "NOT_VERIFIED",
        "instruments": [],
        "raw_response_persisted": False,
        "account_id_logged": False,
        "metadata_proves_spread_betting_account": False,
    }


def _emit(payload: dict[str, Any], secrets: tuple[str, ...]) -> None:
    ipc = _load("credential_ipc")
    text = json.dumps(payload, sort_keys=True)
    if ipc.contains_exact(text, secrets):
        text = json.dumps(_fail("SENSITIVE_OUTPUT_BLOCKED", real=payload.get("data_source") == "REAL_OANDA_LIVE_INSTRUMENT_METADATA"), sort_keys=True)
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def _run(public: dict[str, Any], header: str, account_id: str, *, harness: bool, deadline_at: float) -> dict[str, Any]:
    gate = _load("live_session_gate")
    transport_mod = _load("restricted_live_transport")
    extract = _load("metadata_extract")
    real = not harness
    authorisation = public.get("authorisation")
    presented = authorisation.get("capability") if isinstance(authorisation, dict) else ""
    if not isinstance(presented, str):
        return _fail("GRANT_REJECTED", real=real)
    stall = public.get("stall")
    if stall == "delay-then-hang":
        time.sleep(0.35)
    digest = hashlib.sha256(presented.encode("utf-8")).hexdigest()
    sys.stdout.write(json.dumps({"ready": True, "step": "instruments", "capability_sha256": digest}) + "\n")
    sys.stdout.flush()
    ack = sys.stdin.buffer.readline(32).strip()
    if ack != b"CAP_OK":
        return _fail("CAPABILITY_REJECTED", real=real)
    if stall == "malformed":
        sys.stdout.write("{not-json\n")
        sys.stdout.flush()
        os._exit(0)
    if stall == "exit":
        os._exit(3)
    if stall == "hang" or stall == "delay-then-hang":
        time.sleep(30)
        return _fail("CHILD_STALLED", real=real)
    if harness:
        grant = gate.bind_harness_grant(public.get("session_id"), "instruments")
        document = public.get("document") if isinstance(public.get("document"), dict) else {}
        connection = transport_mod.HarnessConnection(document)
    else:
        grant = gate.note_parent_ack("CAP_OK", public.get("session_id"), "instruments")
        connection = None
    exchange = transport_mod.LiveExchange(connection)
    transport = transport_mod.RestrictedLiveTransport(exchange, grant, str(public.get("session_id")))
    try:
        raw = transport.get_instruments(account_id, authorization_header=header, deadline_at=deadline_at)
        try:
            document = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            return _fail("MALFORMED_RESPONSE", real=real)
        instruments = extract.extract(document)
    except transport_mod.TransportRejected as exc:
        return _fail(exc.code, real=real)
    except extract.MetadataRejected as exc:
        return _fail(exc.code, real=real)
    finally:
        gate.expire_grant(grant)
    result = _fail("NONE", real=real)
    result["error_code"] = "NONE"
    result["instruments"] = instruments
    result["broker_response_received"] = True
    return result


def _child(*, harness: bool) -> int:
    gate = _load("live_session_gate")
    ipc = _load("credential_ipc")
    if harness:
        _tripwire_https()
    else:
        try:
            gate.assert_real_session()
        except gate.GateRejected as exc:
            _emit(_fail(exc.code, real=True), ())
            return 2
    try:
        raw = sys.stdin.buffer.readline(ipc.MAX_FRAME + 2)
        if len(raw) > ipc.MAX_FRAME + 1:
            raise ipc.IpcRejected("IPC_TOO_LARGE")
        if harness:
            public, header, account_id = ipc.consume_authenticated(raw)
        else:
            public, header, account_id = ipc.consume_real(raw)
    except Exception as exc:
        code = exc.code if isinstance(exc, ipc.IpcRejected) else "IPC_REJECTED"
        _emit(_fail(code, real=not harness), ())
        return 1
    secrets = (account_id, header)
    authorisation = public.get("authorisation") if isinstance(public.get("authorisation"), dict) else {}
    capability = authorisation.get("capability")
    if isinstance(capability, str):
        secrets = secrets + (capability,)
    deadline_at = time.monotonic() + 5
    try:
        result = _run(public, header, account_id, harness=harness, deadline_at=deadline_at)
    except Exception:
        result = _fail("EXCEPTION_CONTAINED", real=not harness)
    finally:
        header = ""
    try:
        sys.stdin.close()
    except Exception:
        pass
    result["ipc_closed"] = True
    _emit(result, secrets)
    return 0 if result.get("error_code") == "NONE" else 1


def main(argv: list[str]) -> int:
    if argv == ["--authenticated-worker", "--harness-transport"]:
        return _child(harness=True)
    if argv == ["--authenticated-worker"]:
        return _child(harness=False)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""Parent for one instrument-metadata child. The real path refuses while the source switch is off.

R.61 copy of the R.60 parent. Protocol identifiers stay on the R.59 contract.
Loader cache names use the r61_ prefix so this tree does not alias R.59 or R.60.
Process creation stays synchronous. The session deadline is checked again immediately
before Popen; a blocked Popen is not interrupted.
"""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WORKER = HERE / "diagnostic_worker.py"
_SAFE_ENV = ("SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATH", "PATHEXT", "TEMP", "TMP")


class SupervisorRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ChildTracker:
    def __init__(self) -> None:
        self.procs: list[subprocess.Popen[bytes]] = []

    def add(self, proc: subprocess.Popen[bytes]) -> None:
        self.procs.append(proc)

    def cleanup(self) -> None:
        for proc in self.procs:
            if proc.poll() is None:
                try:
                    proc.kill()
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
            # A full Windows write pipe blocks inside stdin.close(). Close it
            # only after the child has exited. Read ends are still released.
            if proc.poll() is not None:
                try:
                    if proc.stdin is not None and not proc.stdin.closed:
                        proc.stdin.close()
                except (AttributeError, OSError, ValueError):
                    pass
            for pipe in (proc.stdout, proc.stderr):
                try:
                    if pipe is not None and not pipe.closed:
                        pipe.close()
                except (AttributeError, OSError, ValueError):
                    pass


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


def child_env() -> dict[str, str]:
    env = {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1", "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    for key in _SAFE_ENV:
        value = os.environ.get(key)
        if value:
            env[key] = value
    return env


def new_session_id() -> str:
    return "r59-" + __import__("secrets").token_hex(16)


def _sensitive(text: str, secrets: tuple[str, ...]) -> bool:
    return _load("credential_ipc").contains_exact(text, secrets)


def _record(
    *,
    collected: str,
    session: str,
    payload: dict[str, Any] | None,
    error: str,
    terminated: bool,
    alive: bool,
    children: int,
    elapsed: float,
    dispatch_mode: str,
    session_authorised: bool,
    attempted: bool,
    received: bool,
) -> dict[str, Any]:
    gate = _load("live_session_gate")
    plan = gate.fixed_plan()
    complete = error == "NONE" and not terminated and not alive and received
    instruments = payload.get("instruments") if isinstance(payload, dict) and error == "NONE" else []
    return {
        "schema_version": "r59.metadata.1",
        "collected_at": collected,
        "session_id": session,
        "plan_id": plan["plan_id"],
        "program": "r59.real_session_entry",
        "data_source": "REAL_OANDA_LIVE_INSTRUMENT_METADATA" if dispatch_mode == "REAL" else "HARNESS_INSTRUMENT_METADATA",
        "session_status": "SESSION_COMPLETE_INSTRUMENT_METADATA" if complete else "SESSION_INCOMPLETE",
        "error_code": error,
        "live_network_access": "REAL_NETWORK_COMPLETED" if complete and dispatch_mode == "REAL" else "REAL_NETWORK_NOT_COMPLETED",
        "network_permitted": bool(session_authorised and dispatch_mode == "REAL"),
        "network_attempted": attempted,
        "broker_response_received": received,
        "real_session_source_enablement": gate.REAL_SESSION_SOURCE_ENABLEMENT is True,
        "executable_order": "NOT_PRODUCED",
        "order_payload": "NOT_PRODUCED",
        "spread_betting_classification": "NOT_VERIFIED",
        "stake_to_unit_mapping": "NOT_VERIFIED",
        "metadata_proves_spread_betting_account": False,
        "account_id_logged": False,
        "raw_response_persisted": False,
        "children_started": children,
        "child_alive": alive,
        "child_terminated": terminated,
        "observed_wall_seconds": round(elapsed, 4),
        "request": {
            "method": "GET",
            "host": plan["host"],
            "port": plan["port"],
            "path": plan["path"],
            "query": plan["query"],
            "redirects": False,
            "retries": 0,
        },
        "instruments": instruments,
        "record_persisted": False,
    }


def _ipc_send(stream: Any, payload: bytes, deadline_at: float, *, close: bool) -> str:
    """Write and flush one IPC message without passing the session deadline.

    A timed-out write returns without closing the pipe. Closing a full Windows
    pipe flushes, and that flush blocks until the child reads or exits. The
    caller kills the child first; only then is stdin closed.
    """
    if deadline_at - time.monotonic() <= 0:
        return "deadline"
    status: dict[str, str] = {}

    def _send() -> None:
        try:
            stream.write(payload)
            stream.flush()
            if close and not stream.closed:
                stream.close()
            status["result"] = "ok"
        except Exception:
            status["result"] = "broken"

    worker = threading.Thread(target=_send, daemon=True)
    worker.start()
    remaining = deadline_at - time.monotonic()
    if remaining < 0:
        remaining = 0.0
    worker.join(remaining)
    if worker.is_alive():
        return "deadline"
    return status.get("result", "broken")


def _stage_budget(deadline_at: float, request_deadline: float) -> tuple[float, bool]:
    """Wait budget for one stage. The session deadline stays where it was set."""
    remaining = deadline_at - time.monotonic()
    if remaining <= 0:
        return 0.0, True
    if remaining <= request_deadline:
        return remaining, True
    return request_deadline, False


def _release_untracked(proc: subprocess.Popen[bytes]) -> None:
    """Last resort when the process object cannot be stored. Bounded, and not a success claim."""
    try:
        if proc.poll() is None:
            proc.kill()
    except OSError:
        pass
    try:
        proc.wait(timeout=5)
    except Exception:
        pass
    try:
        alive = proc.poll() is None
    except Exception:
        alive = True
    if not alive:
        try:
            if proc.stdin is not None and not proc.stdin.closed:
                proc.stdin.close()
        except (AttributeError, OSError, ValueError):
            pass
    for pipe in (proc.stdout, proc.stderr):
        try:
            if pipe is not None and not pipe.closed:
                pipe.close()
        except (AttributeError, OSError, ValueError):
            pass


def _reap(proc: subprocess.Popen[bytes], reader: threading.Thread | None = None) -> bool:
    if proc.poll() is None:
        try:
            proc.kill()
        except OSError:
            pass
    if reader is not None and reader.is_alive():
        reader.join(1)
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
    if proc.poll() is None:
        return True
    try:
        if proc.stdin is not None and not proc.stdin.closed:
            proc.stdin.close()
    except (AttributeError, OSError, ValueError):
        pass
    return False


def _drop(path: Path) -> None:
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        pass


def _persist_record(directory: Path, session_id: str, payload: bytes) -> None:
    """Atomically publish one record. A failure leaves no successful file."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (session_id + ".json")
    temporary = directory / (session_id + ".json.tmp")
    _drop(temporary)
    fd = os.open(str(temporary), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        offset = 0
        while offset < len(payload):
            wrote = os.write(fd, payload[offset:])
            if wrote <= 0:
                raise OSError("short write")
            offset += wrote
        os.fsync(fd)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        _drop(temporary)
        raise
    try:
        os.close(fd)
    except OSError:
        _drop(temporary)
        raise
    try:
        os.replace(str(temporary), str(target))
    except Exception:
        _drop(temporary)
        raise


def _mark_persistence_failed(record: dict[str, Any]) -> dict[str, Any]:
    record["error_code"] = "RECORD_PERSISTENCE_FAILED"
    record["session_status"] = "SESSION_INCOMPLETE"
    record["record_persisted"] = False
    record["live_network_access"] = "REAL_NETWORK_NOT_COMPLETED"
    return record


def _spawn(
    *,
    session_id: str,
    collected_at: str,
    account_id: str,
    token: str,
    document: dict[str, Any] | None,
    stall: str | None,
    request_deadline: float,
    deadline_at: float,
    dispatch_mode: str,
    issuer: Any,
    tracker: ChildTracker,
    fault_at: str | None,
) -> tuple[dict[str, Any] | None, bool, bool, str]:
    gate = _load("live_session_gate")
    ipc = _load("credential_ipc")
    if deadline_at - time.monotonic() <= 0:
        raise SupervisorRejected("SESSION_DEADLINE")
    mode = "REAL_SESSION" if dispatch_mode == "REAL" else "HARNESS_SESSION"
    if dispatch_mode == "REAL":
        gate.assert_real_session()
    capability = issuer.issue(session_id=session_id, step="instruments", mode=mode, lifetime=max(0.1, deadline_at - time.monotonic()))
    public = {
        "mode": mode,
        "step": "instruments",
        "prior": [],
        "session_id": session_id,
        "collected_at": collected_at,
    }
    authorisation = {
        "kind": mode,
        "session_id": session_id,
        "step": "instruments",
        "host": gate.LIVE_HOST,
        "port": gate.LIVE_PORT,
        "plan_id": gate.PLAN_ID,
        "capability": capability,
    }
    frame = ipc.authenticated_frame(
        public,
        account_id=account_id,
        token=token,
        authorisation=authorisation,
        document=document if dispatch_mode != "REAL" else None,
        stall=stall,
    )
    sent = "broken"
    try:
        if deadline_at - time.monotonic() <= 0:
            raise SupervisorRejected("SESSION_DEADLINE")
        argv = [sys.executable, "-B", str(WORKER), "--authenticated-worker"]
        if dispatch_mode != "REAL":
            argv.append("--harness-transport")
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=child_env(), cwd=str(HERE))
        try:
            tracker.add(proc)
        except Exception:
            try:
                tracker.procs.append(proc)
            except Exception:
                _release_untracked(proc)
                raise
            raise
        assert proc.stdin is not None and proc.stdout is not None
        if fault_at == "after_spawn":
            raise RuntimeError("SESSION_FAILED")
        sent = _ipc_send(proc.stdin, frame + b"\n", deadline_at, close=False)
    finally:
        del frame
    if sent == "deadline":
        alive = _reap(proc)
        return None, True, alive, "SESSION_DEADLINE"
    if sent != "ok":
        alive = _reap(proc)
        return None, False, alive, ""
    holder: dict[str, bytes] = {}

    def _read_ready() -> None:
        holder["line"] = proc.stdout.readline()

    reader = threading.Thread(target=_read_ready, daemon=True)
    reader.start()
    ready_budget, ready_bounded = _stage_budget(deadline_at, request_deadline)
    if ready_budget <= 0:
        alive = _reap(proc, reader)
        return None, True, alive, "SESSION_DEADLINE"
    reader.join(ready_budget)
    if reader.is_alive():
        alive = _reap(proc, reader)
        return None, True, alive, "SESSION_DEADLINE" if ready_bounded else ""
    try:
        ready = json.loads(holder.get("line", b"").decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        ready = None
    if isinstance(ready, dict) and ready.get("ready") is not True and ready.get("executable_order") == "NOT_PRODUCED":
        try:
            if proc.stdin is not None and not proc.stdin.closed:
                proc.stdin.close()
        except Exception:
            pass
        remaining = deadline_at - time.monotonic()
        if remaining <= 0:
            alive = _reap(proc, reader)
            return None, True, alive, "SESSION_DEADLINE"
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            alive = _reap(proc, reader)
            return None, True, alive, "SESSION_DEADLINE"
        except Exception:
            alive = _reap(proc, reader)
            return None, False, alive, ""
        return ready, False, proc.poll() is None, ""
    approved = False
    if isinstance(ready, dict) and ready.get("ready") is True and ready.get("step") == "instruments":
        expected = hashlib.sha256(capability.encode("utf-8")).hexdigest()
        presented = ready.get("capability_sha256")
        if isinstance(presented, str) and len(presented) == len(expected) and hmac.compare_digest(presented, expected):
            try:
                issuer.redeem(capability, session_id=session_id, step="instruments", mode=mode)
            except gate.GateRejected:
                approved = False
            else:
                approved = True
    ack = b"CAP_OK\n" if approved else b"CAP_NO\n"
    sent = _ipc_send(proc.stdin, ack, deadline_at, close=True)
    del ack
    if sent == "deadline":
        alive = _reap(proc, reader)
        return None, True, alive, "SESSION_DEADLINE"
    if sent != "ok":
        alive = _reap(proc, reader)
        return None, False, alive, ""
    completion_budget, completion_bounded = _stage_budget(deadline_at, request_deadline)
    if completion_budget <= 0:
        alive = _reap(proc, reader)
        return None, True, alive, "SESSION_DEADLINE"
    try:
        # The acknowledgement writer already closed stdin. CPython 3.12 on
        # Linux flushes that stream inside communicate() and raises ValueError
        # once it is closed. Drop the closed handle so the read still runs.
        if proc.stdin is not None and proc.stdin.closed:
            proc.stdin = None
        out, err = proc.communicate(timeout=completion_budget)
    except subprocess.TimeoutExpired:
        alive = _reap(proc, reader)
        return None, True, alive, "SESSION_DEADLINE" if completion_bounded else ""
    text = out.decode("utf-8", errors="replace") + err.decode("utf-8", errors="replace")
    secrets = (account_id, token, capability, "Bearer " + token, "Authorization: Bearer " + token)
    if _sensitive(text, secrets):
        return {"error_code": "SENSITIVE_OUTPUT_BLOCKED", "executable_order": "NOT_PRODUCED", "instruments": []}, False, False, ""
    if not out.strip():
        return None, False, proc.poll() is None, ""
    try:
        payload = json.loads(out.decode("utf-8"))
    except json.JSONDecodeError:
        return {"error_code": "MALFORMED_CHILD_RESULT", "executable_order": "NOT_PRODUCED", "instruments": []}, False, False, ""
    if not isinstance(payload, dict) or payload.get("step") != "instruments" or payload.get("executable_order") != "NOT_PRODUCED":
        return {"error_code": "MALFORMED_CHILD_RESULT", "executable_order": "NOT_PRODUCED", "instruments": []}, False, False, ""
    if payload.get("raw_response_persisted") is not False or payload.get("account_id_logged") is not False:
        return {"error_code": "SENSITIVE_OUTPUT_BLOCKED", "executable_order": "NOT_PRODUCED", "instruments": []}, False, False, ""
    return payload, False, proc.poll() is None, ""


def _execute(
    *,
    dispatch_mode: str,
    account_id: str,
    token: str,
    document: dict[str, Any] | None,
    stall: str | None,
    request_deadline: float,
    session_deadline: float,
    log_dir: Path,
    session_id: str,
    collected_at: str,
    fault_at: str | None,
    session_authorised: bool,
) -> dict[str, Any]:
    if request_deadline <= 0 or request_deadline > 5 or session_deadline <= 0 or session_deadline > 15:
        raise SupervisorRejected("DEADLINE_ABOVE_CAP")
    gate = _load("live_session_gate")
    if dispatch_mode == "REAL":
        gate.assert_real_session()
    elif dispatch_mode != "HARNESS":
        raise SupervisorRejected("MODE_REJECTED")
    issuer = gate.CapabilityIssuer()
    tracker = ChildTracker()
    started = time.monotonic()
    deadline_at = started + session_deadline
    error = "NONE"
    payload = None
    terminated = False
    alive = False
    children = 0
    try:
        payload, terminated, alive, deadline_status = _spawn(
            session_id=session_id,
            collected_at=collected_at,
            account_id=account_id,
            token=token,
            document=document,
            stall=stall,
            request_deadline=request_deadline,
            deadline_at=deadline_at,
            dispatch_mode=dispatch_mode,
            issuer=issuer,
            tracker=tracker,
            fault_at=fault_at,
        )
        if deadline_status == "SESSION_DEADLINE":
            error = "SESSION_DEADLINE"
            terminated = True
        elif terminated:
            error = "CHILD_TERMINATED"
        elif not isinstance(payload, dict):
            error = "CHILD_CRASHED"
        elif payload.get("error_code") != "NONE":
            error = str(payload.get("error_code"))
    except SupervisorRejected as exc:
        error = exc.code
    except KeyboardInterrupt:
        error = "SESSION_INTERRUPTED"
        terminated = True
    except Exception:
        error = "SESSION_FAILED"
        terminated = True
    finally:
        cleanup_failed = False
        try:
            tracker.cleanup()
            if fault_at == "cleanup":
                raise OSError("cleanup")
        except Exception:
            cleanup_failed = True
            try:
                tracker.cleanup()
            except Exception:
                pass
        try:
            issuer.expire_all()
        except Exception:
            cleanup_failed = True
        try:
            alive = any(proc.poll() is None for proc in tracker.procs)
        except Exception:
            cleanup_failed = True
            alive = True
        children = len(tracker.procs)
        if cleanup_failed and error == "NONE":
            error = "CHILD_CLEANUP_FAILED"
    received = (
        session_authorised
        and dispatch_mode == "REAL"
        and error == "NONE"
        and isinstance(payload, dict)
        and payload.get("broker_response_received") is True
    )
    attempted = session_authorised and dispatch_mode == "REAL" and children > 0
    record = _record(
        collected=collected_at,
        session=session_id,
        payload=payload if isinstance(payload, dict) else None,
        error=error,
        terminated=terminated,
        alive=alive,
        children=children,
        elapsed=time.monotonic() - started,
        dispatch_mode=dispatch_mode,
        session_authorised=session_authorised,
        attempted=attempted,
        received=received,
    )
    text = json.dumps(record, indent=2, sort_keys=True)
    secrets = (account_id, token, "Bearer " + token)
    if _sensitive(text, secrets):
        record = _record(
            collected=collected_at,
            session=session_id,
            payload=None,
            error="SENSITIVE_OUTPUT_BLOCKED",
            terminated=terminated,
            alive=alive,
            children=children,
            elapsed=time.monotonic() - started,
            dispatch_mode=dispatch_mode,
            session_authorised=session_authorised,
            attempted=False,
            received=False,
        )
        text = json.dumps(record, indent=2, sort_keys=True)
    disk = dict(record)
    disk["record_persisted"] = True
    text = json.dumps(disk, indent=2, sort_keys=True)
    try:
        _persist_record(log_dir, session_id, text.encode("utf-8"))
    except Exception:
        return _mark_persistence_failed(record)
    record["record_persisted"] = True
    return record


def run_harness_session(
    *,
    answer: str,
    account_id: str,
    token: str,
    document: dict[str, Any],
    stall: str | None = None,
    request_deadline: float = 5.0,
    session_deadline: float = 15.0,
    log_dir: Path,
    fault_at: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    gate = _load("live_session_gate")
    screen = gate.render_plan()
    confirmation = gate.confirm_one_session(answer, screen=screen)
    gate.accept_confirmation(confirmation)
    if confirmation.get("network_permitted") is not False:
        raise SupervisorRejected("NETWORK_PERMITTED_REJECTED")
    try:
        gate.issue_runtime_authorisation()
    except gate.GateRejected as exc:
        if exc.code != "REAL_OANDA_SESSION_NOT_AUTHORISED":
            raise
    else:
        raise SupervisorRejected("REAL_GRANT_ISSUED")
    return _execute(
        dispatch_mode="HARNESS",
        account_id=account_id,
        token=token,
        document=document,
        stall=stall,
        request_deadline=request_deadline,
        session_deadline=session_deadline,
        log_dir=log_dir,
        session_id=session_id or new_session_id(),
        collected_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        fault_at=fault_at,
        session_authorised=False,
    )


class _VerifiedRealAuthorisation:
    def __init__(self) -> None:
        _load("live_session_gate").assert_real_session()


def run_real_session(*, reader: Any, log_dir: Path | None = None) -> dict[str, Any]:
    """Refuse before a prompt, a permit read, or a socket while the source switch is off."""
    gate = _load("live_session_gate")
    gate.assert_real_session()
    if gate.fixed_plan()["requests"] != ["instruments"] or gate.fixed_plan()["methods"] != ["GET"]:
        raise gate.GateRejected("PLAN_REJECTED")
    screen = gate.render_plan()
    answer = reader(screen)
    confirmation = gate.confirm_one_session(answer, screen=screen)
    gate.accept_confirmation(confirmation)
    activation = _load("one_session_activation")
    try:
        activation.consume()
    except activation.ActivationRejected as exc:
        raise gate.GateRejected(exc.code) from None
    session_id = new_session_id()
    ipc = _load("credential_ipc")
    grant = gate.issue_runtime_authorisation(
        answer=gate.ONE_SESSION_PHRASE,
        confirmation=confirmation,
        plan=gate.fixed_plan(),
        session_id=session_id,
        step="instruments",
    )
    account_id = ipc.prompt_account_id(grant=grant, session_id=session_id, step="instruments")
    token = ipc.prompt_hidden_token(grant=grant, session_id=session_id, step="instruments")
    gate.expire_grant(grant)
    target = HERE / "real_diagnostic_logs" if log_dir is None else log_dir
    return _execute(
        dispatch_mode="REAL",
        account_id=account_id,
        token=token,
        document=None,
        stall=None,
        request_deadline=5.0,
        session_deadline=15.0,
        log_dir=target,
        session_id=session_id,
        collected_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        fault_at=None,
        session_authorised=isinstance(_VerifiedRealAuthorisation(), _VerifiedRealAuthorisation),
    )

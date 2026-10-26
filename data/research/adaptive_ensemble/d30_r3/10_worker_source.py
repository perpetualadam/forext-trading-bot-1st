"""Synthetic worker fixtures. Fixed modes, one descendant at most."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

MODES = frozenset({
    "complete",
    "nonzero",
    "exception",
    "block",
    "ignore_stop",
    "malformed",
    "stdout_flood",
    "late",
    "secrets",
    "secret_block",
    "spawn_complete",
    "spawn_block",
    "spawn_exit_first",
})
DESCENDANT_MODE = {
    "spawn_complete": "complete",
    "spawn_block": "block",
    "spawn_exit_first": "block",
}


def load_supervisor():
    path = Path(__file__).resolve().parent / "09_supervisor_source.py"
    if path.parent.name != "d30_r3":
        raise SystemExit(2)
    spec = importlib.util.spec_from_file_location("d30r3_supervisor", path)
    if spec is None or spec.loader is None:
        raise SystemExit(2)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def emit(payload: dict[str, str]) -> None:
    sys.stdout.buffer.write(json.dumps(payload).encode("utf-8") + b"\n")
    sys.stdout.flush()


def wait_for_supervisor_decision(path: Path) -> str:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if path.exists():
            text = path.read_text(encoding="utf-8").strip()
            if text in {"resume", "abort"}:
                return text
            return "abort"
        time.sleep(0.02)
    return "abort"


def terminate_without_resume(sup, process_handle: int) -> None:
    sup.KERNEL.TerminateProcess(process_handle, 1)
    sup.wait_handle(process_handle, 2.0)


def contain_descendant(mode: str, workdir: Path, token: str) -> int:
    sup = load_supervisor()
    script = Path(__file__).resolve().parent / "11_descendant_source.py"
    if script.name != "11_descendant_source.py" or script.parent.name != "d30_r3":
        return 2
    argv = [sys.executable, "-B", str(script), DESCENDANT_MODE[mode]]
    spawned = sup.spawn_suspended(argv, workdir, sup.minimal_env(), "nul")
    resumed = False
    try:
        low, high = sup.process_times(spawned.process.value)
        payload = {"pid": spawned.pid, "creation_low": low, "creation_high": high}
        temporary = workdir / f"identity_{token}.json.tmp"
        final = workdir / f"identity_{token}.json"
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(temporary, final)
        decision = wait_for_supervisor_decision(workdir / f"control_{token}.txt")
        ack = workdir / f"ack_{token}.txt"
        if decision != "resume":
            terminate_without_resume(sup, spawned.process.value)
            ack.write_text("aborted\n", encoding="utf-8")
            return 2
        sup.KERNEL.ResumeThread(spawned.thread.value)
        resumed = True
        ack.write_text("resumed\n", encoding="utf-8")
        if mode == "spawn_exit_first":
            return 0
        sup.wait_handle(spawned.process.value, 30.0)
        return 0
    finally:
        if not resumed and spawned.process is not None and sup.still_alive(spawned.process.value):
            terminate_without_resume(sup, spawned.process.value)
        if spawned.thread is not None:
            spawned.thread.close()
        if spawned.process is not None:
            spawned.process.close()


def main() -> int:
    if len(sys.argv) != 4:
        return 2
    mode, workdir_text, token = sys.argv[1:]
    if mode not in MODES or not token.isdigit() or len(token) > 24:
        return 2
    workdir = Path(workdir_text).resolve()
    if workdir.name != "d30_r3" or not workdir.is_dir():
        return 2
    os.chdir(workdir)
    if mode == "complete":
        time.sleep(0.05)
        emit({"kind": "ok", "status": "complete"})
        return 0
    if mode == "nonzero":
        return 3
    if mode == "exception":
        raise RuntimeError("synthetic-exception")
    if mode == "malformed":
        sys.stdout.buffer.write(b"NOT-JSON\n")
        return 0
    if mode == "stdout_flood":
        sys.stdout.buffer.write(b"X" * 40000)
        sys.stdout.flush()
        time.sleep(30)
        return 0
    if mode == "late":
        time.sleep(0.25)
        emit({"kind": "ok", "status": "complete"})
        time.sleep(30)
        return 0
    if mode in {"secrets", "secret_block"}:
        sys.stdout.buffer.write(
            b'{"kind":"ok","status":"complete","note":"synthetic-bearer-redact-me",'
            b'"authorization":"synthetic-authorization-redact-me","cookie":"synthetic-cookie-redact-me",'
            b'"query":"synthetic-signed-query-redact-me","proxy":"synthetic-proxy-redact-me",'
            b'"env":"synthetic-env-redact-me"}\n'
        )
        sys.stdout.flush()
        if mode == "secret_block":
            time.sleep(30)
        return 0
    if mode in DESCENDANT_MODE:
        return contain_descendant(mode, workdir, token)
    time.sleep(30)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

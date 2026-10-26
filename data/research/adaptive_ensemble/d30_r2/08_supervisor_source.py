"""Supervisor for synthetic workers. No sockets and no DNS."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ALLOWED_HOSTS = frozenset({"registry-1.docker.io", "auth.docker.io"})
REPOSITORY = "library/python"
MODES = frozenset({
    "complete",
    "nonzero",
    "exception",
    "block",
    "ignore_stop",
    "silent",
    "malformed",
    "stdout_flood",
    "stderr_flood",
    "partial",
    "late",
    "secrets",
    "env_keys",
    "extend",
})
SECRET_MARKERS = (
    "synthetic-bearer-redact-me",
    "synthetic-authorization-redact-me",
    "synthetic-cookie-redact-me",
    "synthetic-signed-query-redact-me",
    "synthetic-proxy-redact-me",
    "synthetic-env-redact-me",
)
OUTPUT_CAP = 8192


class Reject(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def minimal_env() -> dict[str, str]:
    kept = {}
    for key in ("SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "COMSPEC", "TEMP", "TMP"):
        value = os.environ.get(key)
        if value:
            kept[key] = value
    kept["PYTHONUTF8"] = "1"
    kept["PYTHONDONTWRITEBYTECODE"] = "1"
    return kept


def cleanup_verdict(worker_alive: bool) -> str:
    if worker_alive:
        return "BLOCKED"
    return "reaped"


def redact(value: object) -> object:
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if str(key).lower() in {"authorization", "cookie", "token", "set-cookie", "proxy", "url", "query", "location"}:
                cleaned[key] = "REDACTED"
            else:
                cleaned[key] = redact(item)
        return cleaned
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        for marker in SECRET_MARKERS:
            if marker in value:
                return "REDACTED"
        return value
    return value


class Budget:
    def __init__(self) -> None:
        self.total = 0
        self.head = 0
        self.token = 0
        self.body = 0
        self.redirects_followed = 0
        self.retries = 0
        self.redirects_recorded = 0

    def reserve(self, host: str, method: str, repository: str, digest: str | None, category: str, allowlist: set[str]) -> int:
        if category in {"storage", "registry_get", "layer_body", "retry"}:
            raise Reject(category)
        if host not in ALLOWED_HOSTS:
            raise Reject("host")
        if repository != REPOSITORY:
            raise Reject("repository")
        if method not in {"HEAD", "GET"}:
            raise Reject("method")
        if host == "registry-1.docker.io" and method != "HEAD":
            raise Reject("registry_get")
        if category == "token" and (host != "auth.docker.io" or method != "GET"):
            raise Reject("token method")
        if digest is not None and digest not in allowlist:
            raise Reject("digest")
        if self.total >= 20:
            raise Reject("total")
        if category == "head" and self.head >= 16:
            raise Reject("head")
        if category == "token" and self.token >= 1:
            raise Reject("token")
        self.total += 1
        if category == "head":
            self.head += 1
        if category == "token":
            self.token += 1
        return self.total

    def add_body(self, count: int, limit: int = 1048576) -> None:
        if count < 0 or self.body + count > limit:
            raise Reject("body")
        self.body += count

    def record_redirect(self) -> None:
        self.redirects_recorded += 1

    def apply_worker_message(self, message: dict) -> None:
        return None


class Supervisor:
    def __init__(self, worker_path: Path, out_dir: Path, stage_deadline: float) -> None:
        self.worker_path = worker_path
        self.out_dir = out_dir
        self.stage_deadline = stage_deadline
        self.started = time.monotonic()
        self.budget = Budget()
        self.attempts = 0
        self.ledger: list[dict[str, object]] = []

    def stage_elapsed(self) -> float:
        return time.monotonic() - self.started

    def choose_limit(self, operation_deadline: float) -> tuple[str, float]:
        remaining = self.stage_deadline - self.stage_elapsed()
        if remaining <= 0:
            return "stage", 0.0
        if operation_deadline < remaining:
            return "operation", operation_deadline
        return "stage", remaining

    def run(self, mode: str, operation_deadline: float) -> dict[str, object]:
        if mode not in MODES:
            raise Reject("mode")
        if self.attempts > 0 and mode == "retry":
            raise Reject("retry")
        self.attempts += 1
        reason, limit = self.choose_limit(operation_deadline)
        if limit <= 0:
            return self._closed("stage", None)
        stop_path = self.out_dir / f"_stop_{time.monotonic_ns()}.txt"
        proc = subprocess.Popen(
            [sys.executable, "-B", str(self.worker_path), mode, str(stop_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(self.out_dir),
            env=minimal_env(),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        stdout_parts: list[bytes] = []
        stderr_parts: list[bytes] = []
        overflow = {"hit": False}

        def pump(pipe: object, parts: list[bytes]) -> None:
            assert hasattr(pipe, "read")
            while sum(len(part) for part in parts) < OUTPUT_CAP:
                chunk = pipe.read(1024)
                if not chunk:
                    break
                room = OUTPUT_CAP - sum(len(part) for part in parts)
                parts.append(chunk[:room])
                if len(chunk) > room:
                    overflow["hit"] = True
                    break
            if sum(len(part) for part in parts) >= OUTPUT_CAP:
                overflow["hit"] = True

        out_thread = threading.Thread(target=pump, args=(proc.stdout, stdout_parts))
        err_thread = threading.Thread(target=pump, args=(proc.stderr, stderr_parts))
        out_thread.start()
        err_thread.start()
        begun = time.monotonic()
        termination_requested = False
        termination_method = "none"
        stop_reason = "completed"
        terminated_at = begun
        alive_after_graceful = False
        try:
            while proc.poll() is None:
                elapsed = time.monotonic() - begun
                if self.stage_elapsed() >= self.stage_deadline:
                    stop_reason = "stage"
                    break
                if elapsed >= limit or overflow["hit"]:
                    stop_reason = "output" if overflow["hit"] and elapsed < limit else reason
                    break
                time.sleep(0.02)
            if proc.poll() is None:
                termination_requested = True
                stop_path.write_text("stop\n", encoding="utf-8")
                graceful_deadline = time.monotonic() + 0.15
                while proc.poll() is None and time.monotonic() < graceful_deadline:
                    time.sleep(0.02)
                alive_after_graceful = proc.poll() is None
                if proc.poll() is None:
                    termination_method = "terminate"
                    terminated_at = time.monotonic()
                    proc.terminate()
                    try:
                        proc.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        termination_method = "kill"
                        proc.kill()
                        proc.wait(timeout=2.0)
                else:
                    termination_method = "graceful"
                    terminated_at = time.monotonic()
            else:
                terminated_at = time.monotonic()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=2.0)
            out_thread.join(timeout=1.0)
            err_thread.join(timeout=1.0)
            if proc.stdout is not None:
                proc.stdout.close()
            if proc.stderr is not None:
                proc.stderr.close()
            if stop_path.exists():
                stop_path.unlink()
        exit_code = proc.poll()
        alive = proc.poll() is None
        raw = b"".join(stdout_parts)
        accepted = False
        parsed: object = None
        if stop_reason == "completed" and not alive:
            try:
                parsed = json.loads(raw.decode("utf-8"))
                if isinstance(parsed, dict):
                    self.budget.apply_worker_message(parsed)
                    parsed = redact(parsed)
                    accepted = True
            except json.JSONDecodeError:
                accepted = False
        elapsed = time.monotonic() - begun
        record = {
            "mode": mode,
            "stop_reason": stop_reason,
            "configured_limit": round(limit, 4),
            "elapsed": round(elapsed, 4),
            "termination_requested": termination_requested,
            "termination_method": termination_method,
            "alive_after_graceful_request": alive_after_graceful,
            "exit_observed": exit_code is not None,
            "exit_code": exit_code,
            "worker_alive_after_cleanup": alive,
            "accepted": accepted,
            "terminated_at": round(terminated_at - begun, 4),
            "cleanup_elapsed": round(time.monotonic() - terminated_at, 4),
            "stdout_bytes": len(raw),
            "stderr_bytes": len(b"".join(stderr_parts)),
            "clock": "monotonic",
        }
        if accepted and isinstance(parsed, dict):
            record["redacted_keys"] = sorted(str(key) for key in parsed)
        self.ledger.append({"mode": mode, "accepted": accepted, "payload": parsed if accepted else "REJECTED"})
        return record

    def _closed(self, reason: str, proc: object) -> dict[str, object]:
        return {
            "mode": "not_started",
            "stop_reason": reason,
            "configured_limit": 0.0,
            "elapsed": 0.0,
            "termination_requested": False,
            "termination_method": "none",
            "exit_observed": False,
            "exit_code": None,
            "worker_alive_after_cleanup": False,
            "accepted": False,
            "terminated_at": 0.0,
            "cleanup_elapsed": 0.0,
            "stdout_bytes": 0,
            "stderr_bytes": 0,
            "clock": "monotonic",
        }

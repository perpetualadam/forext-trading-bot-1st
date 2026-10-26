"""Synthetic worker fixtures. No sockets, DNS, or project imports."""
from __future__ import annotations

import json
import os
import sys
import time

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


def emit(payload: dict) -> None:
    sys.stdout.buffer.write(json.dumps(payload).encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in MODES:
        sys.exit(9)
    mode = sys.argv[1]
    if mode == "complete":
        time.sleep(0.08)
        emit({"kind": "ok"})
    elif mode == "nonzero":
        sys.exit(3)
    elif mode == "exception":
        raise RuntimeError("synthetic worker failure")
    elif mode == "block":
        time.sleep(4.0)
        emit({"kind": "late"})
    elif mode == "ignore_stop":
        time.sleep(4.0)
        emit({"kind": "ignored"})
    elif mode == "silent":
        time.sleep(4.0)
    elif mode == "malformed":
        sys.stdout.buffer.write(b"NOT-JSON\n")
    elif mode == "stdout_flood":
        sys.stdout.buffer.write(b"X" * 40000)
        sys.stdout.buffer.flush()
        time.sleep(4.0)
    elif mode == "stderr_flood":
        sys.stderr.buffer.write(b"Y" * 40000)
        sys.stderr.buffer.flush()
        time.sleep(4.0)
    elif mode == "partial":
        sys.stdout.buffer.write(b"{")
        sys.stdout.buffer.flush()
    elif mode == "late":
        time.sleep(1.2)
        emit({"kind": "late"})
    elif mode == "secrets":
        emit({
            "kind": "ok",
            "authorization": "synthetic-bearer-redact-me",
            "cookie": "synthetic-cookie-redact-me",
            "token": "synthetic-authorization-redact-me",
            "url": "synthetic-signed-query-redact-me",
            "proxy": "synthetic-proxy-redact-me",
            "note": "synthetic-env-redact-me",
        })
    elif mode == "env_keys":
        emit({"kind": "env", "keys": sorted(os.environ)})
    elif mode == "extend":
        emit({"kind": "ok", "extend_deadline_seconds": 999})
    sys.exit(0)


if __name__ == "__main__":
    main()

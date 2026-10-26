"""Operator entry for one future instrument-metadata read.

Run from the project root with no arguments. Any argument is refused.
While the source switch is off, the process does not prompt and does not open a socket.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFUSAL = "R59 instrument metadata session is not authorised. No credential prompt. No network connection."


def _load(stem: str):
    name = f"r59_{stem}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, HERE / f"{stem}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def reader(screen: str) -> str:
    print(screen, flush=True)
    return input("Confirmation: ")


def launch(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args:
        print(REFUSAL)
        return 2
    supervisor = _load("diagnostic_supervisor")
    try:
        supervisor.run_real_session(reader=reader)
    except KeyboardInterrupt:
        print("SESSION_INTERRUPTED")
        return 2
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code == "REAL_OANDA_SESSION_NOT_AUTHORISED":
            print(REFUSAL)
            return 2
        if isinstance(code, str):
            print(code)
            return 2
        print("SESSION_FAILED")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(launch())

"""Prepare one future real diagnostic permit. This does not start a session.

The source switch is required. While it is off, this command creates nothing.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFUSAL = "R56 one-session activation is not authorised. No permit was created. No network connection."


def _load(stem: str):
    name = f"r56p6_{stem}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, HERE / f"{stem}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def launch(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args:
        print(REFUSAL)
        return 2
    try:
        _load("one_session_activation").prepare()
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code == "REAL_OANDA_SESSION_NOT_AUTHORISED":
            print(REFUSAL)
            return 2
        if isinstance(code, str):
            print(code)
            return 2
        print(REFUSAL)
        return 2
    print("ONE_SESSION_PERMIT_CREATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(launch())

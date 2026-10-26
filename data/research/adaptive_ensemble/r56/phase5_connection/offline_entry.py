"""Offline entry. Live, connect, and authenticate arguments fail closed."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DISABLED = "R56 phase 5 read-only connection is offline. No credential prompt. No network connection."


def _load(stem: str):
    name = f"r56p5_{stem}"
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
    """Accept only --offline. Every other argument returns exit code 2."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args != ["--offline"]:
        print(DISABLED)
        return 2
    confirmation = _load("operator_confirmation")
    credentials = _load("credential_gate")
    supervisor = _load("session_supervisor")
    record = supervisor.run_offline(answer=confirmation.SYNTHETIC_PHRASE, credential=credentials.SyntheticCredential())
    if record.get("session_status") != supervisor.COMPLETE or record.get("live_network_access") != "NOT_AUTHORISED":
        print(DISABLED)
        return 1
    if record.get("network_permitted") is not False or record.get("executable_order") != "NOT_PRODUCED":
        print(DISABLED)
        return 1
    print(DISABLED)
    return 0


if __name__ == "__main__":
    raise SystemExit(launch())

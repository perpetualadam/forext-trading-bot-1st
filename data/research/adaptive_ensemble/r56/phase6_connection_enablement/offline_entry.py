"""Offline entry. Real mode is not started from this file."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PHASE5 = HERE.parent / "phase5_connection"
DISABLED = "R56 phase 6 connection enablement is offline. No credential prompt. No network connection."


def _load(directory: Path, prefix: str, stem: str):
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


def launch_authenticated(*_args: object, **_kwargs: object) -> int:
    """The authenticated process entry is present and refused. It does not read credentials."""
    print(DISABLED)
    return 2


def launch(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args != ["--offline"]:
        print(DISABLED)
        return 2
    gate = _load(HERE, "r56p6", "live_session_gate")
    if gate.REAL_SESSION_SOURCE_ENABLEMENT is True:
        print(DISABLED)
        return 2
    confirmation = _load(PHASE5, "r56p5", "operator_confirmation")
    credentials = _load(PHASE5, "r56p5", "credential_gate")
    supervisor = _load(HERE, "r56p6", "diagnostic_supervisor")
    record = supervisor.run_offline(answer=confirmation.SYNTHETIC_PHRASE, credential=credentials.SyntheticCredential())
    if record.get("session_status") != supervisor.COMPLETE or record.get("live_network_access") != "NOT_AUTHORISED":
        print(DISABLED)
        return 1
    if record.get("real_session_source_enablement") is not False or record.get("executable_order") != "NOT_PRODUCED":
        print(DISABLED)
        return 1
    print(DISABLED)
    return 0


if __name__ == "__main__":
    raise SystemExit(launch())

"""Offline entry. There is no live, connect, or authenticate mode."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DISABLED = "R56 phase 4 diagnostic preparation is offline. No credential prompt. No network connection."


def _load(stem: str):
    name = f"r56p4_{stem}"
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
    transport = _load("https_transport_candidate")
    fixtures = _load("synthetic_transport")
    session = _load("diagnostic_session")
    clock = transport.SessionClock(monotonic=transport.ManualClock())
    double = fixtures.OfflineDouble()
    record = session.run_offline(double, clock=clock)
    if record.get("session_status") != session.COMPLETE or record.get("live_network_access") != "NOT_AUTHORISED":
        print(DISABLED)
        return 1
    print(DISABLED)
    return 0


if __name__ == "__main__":
    raise SystemExit(launch())

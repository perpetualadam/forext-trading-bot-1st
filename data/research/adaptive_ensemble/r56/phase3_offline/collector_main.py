"""Offline entry for the R.56 phase 3 collector. There is no live mode."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DISABLED = "R56 phase 3 collector is offline. No credential prompt. No network connection."


def _load(stem: str):
    name = f"r56p3_{stem}"
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
    fixtures = _load("synthetic_fixtures")
    transport_mod = _load("offline_transport")
    session = _load("collector_session")
    transport = transport_mod.SyntheticTransport(fixtures.summary_document(), fixtures.pricing_document())
    record = session.run_synthetic(transport)
    if record.get("session_status") != session.COMPLETE or record.get("executable_order") != "NOT_PRODUCED":
        print(DISABLED)
        return 1
    print(DISABLED)
    return 0


if __name__ == "__main__":
    raise SystemExit(launch())

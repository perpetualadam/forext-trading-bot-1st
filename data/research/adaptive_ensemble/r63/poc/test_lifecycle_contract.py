"""Contract checks that do not depend on a platform-specific kill domain."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lifecycle_contract import (  # noqa: E402
    CONTAINMENT_UNAVAILABLE,
    REQUIRE_DESCENDANT_CONTAINMENT,
    ProcessLifecycleManager,
)


def test_probe_names_the_host_and_does_not_treat_availability_as_activation() -> None:
    report = ProcessLifecycleManager().probe_capabilities()
    assert report["operating_system"]
    assert report["requested_policy"] == REQUIRE_DESCENDANT_CONTAINMENT
    assert "actual_if_requested" in report
    assert report["actual_if_requested"] != "DESCENDANT_CONTAINMENT_ACTIVE"
    assert "unsupported" in report


@pytest.mark.skipif(sys.platform == "win32", reason="Linux refusal path")
def test_default_policy_does_not_execute_without_descendant_containment(tmp_path: Path) -> None:
    manager = ProcessLifecycleManager()
    session = manager.run("side", time.monotonic() + 5, tmp_path)
    try:
        assert session.error == CONTAINMENT_UNAVAILABLE
        assert session.actual_containment == CONTAINMENT_UNAVAILABLE
        assert session.pid == 0
        assert session.worker_executed is False
        assert not (tmp_path / "side.txt").exists()
    finally:
        manager.cleanup(session)


def test_sources_do_not_touch_trading_or_credentials() -> None:
    banned = (
        "forex_bot",
        "oanda",
        "load_dotenv",
        "import requests",
        "import httpx",
        "diagnostic_supervisor",
        "live_session_gate",
        ".env",
    )
    for path in HERE.glob("*.py"):
        if path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8").lower()
        for item in banned:
            assert item not in text

"""Eligibility is the audited byte identity, not a global flag."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
R61 = HERE.parents[1] / "r61"

from worker_eligibility import AUDITED_SHA256, evaluate  # noqa: E402


def test_current_r61_worker_matches_the_audited_manifest() -> None:
    result = evaluate(R61)
    assert result["eligible"] is True
    assert result["global_bypass"] is False
    assert result["equivalent_to_descendant_containment"] is False
    assert result["default_policy"] == "REQUIRE_DESCENDANT_CONTAINMENT"
    assert result["policy_if_explicitly_selected"] == "DIRECT_CHILD_ONLY_EXPLICIT"
    assert result["mismatches"] == ()
    assert set(result["observed"]) == set(AUDITED_SHA256)


def test_one_changed_byte_removes_eligibility(tmp_path: Path) -> None:
    for name in AUDITED_SHA256:
        data = (R61 / name).read_bytes()
        (tmp_path / name).write_bytes(data)
    target = tmp_path / "diagnostic_worker.py"
    target.write_bytes(target.read_bytes() + b"\n# subprocess.Popen\n")
    result = evaluate(tmp_path)
    assert result["eligible"] is False
    assert result["policy_if_explicitly_selected"] == "NOT_ELIGIBLE"
    assert "diagnostic_worker.py" in result["mismatches"]
    assert result["global_bypass"] is False


def test_a_missing_loaded_module_removes_eligibility(tmp_path: Path) -> None:
    for name in AUDITED_SHA256:
        if name == "credential_ipc.py":
            continue
        (tmp_path / name).write_bytes((R61 / name).read_bytes())
    result = evaluate(tmp_path)
    assert result["eligible"] is False
    assert result["missing"] == ("credential_ipc.py",)


def test_sources_do_not_touch_trading_or_credentials() -> None:
    banned = ("forex_bot", "load_dotenv", "diagnostic_supervisor", "sudo", ".env", "api-fxtrade")
    for path in HERE.glob("*.py"):
        if path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8").lower()
        for item in banned:
            assert item not in text

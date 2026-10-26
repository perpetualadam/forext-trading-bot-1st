"""Stage D.5 actual-lifespan checks. The runner imports app.py, this module does not."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = Path(__file__).resolve().parent / "d5_lifespan_runner.py"
EXPECTED = {
    "app.py": "f38c304c4692c4a69e537610173e5691c03d49e24c48d6e258f56d1be75ae7b4",
    "live_safety.py": "11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44",
    "strategy_meta.py": "492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d",
}
DOWNSTREAM = (
    "get_connection",
    "build_api",
    "fetch_account_summary",
    "run_reconciliation_once",
    "create_task",
    "run_bot",
    "start_telegram_control",
    "load_open_orders",
    "load_reconcile_state",
    "alert",
    "requests",
    "psycopg2.connect",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _case(report: dict, name: str) -> dict:
    return report["cases"][name]


def _zero_downstream(case: dict) -> None:
    counts = case["counts"]
    for name in DOWNSTREAM:
        assert counts.get(name, 0) == 0
    assert not any(str(key).startswith("order_route:") for key in counts)
    assert case["network"] == []
    assert "synthetic-marker" not in case["message"]
    assert "secret_marker" not in case["message"]
    assert case["auth"] == "BLOCKED"
    assert case["active"] == []


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    for name, digest in EXPECTED.items():
        assert _sha(ROOT / "forex_bot" / name) == digest
    work = tmp_path_factory.mktemp("d5-lifespan")
    safety = work / "safety.json"
    out = work / "report.json"
    inherited = {
        key: os.environ[key]
        for key in (
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "COMSPEC",
            "PATHEXT",
            "TEMP",
            "TMP",
            "SYSTEMDRIVE",
            "APPDATA",
            "LOCALAPPDATA",
            "USERPROFILE",
            "HOMEDRIVE",
            "HOMEPATH",
        )
        if key in os.environ
    }
    env = {
        **inherited,
        "PYTHONPATH": str(ROOT),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_CURRENT_TEST": "d5-isolated-lifespan",
        "LIVE_SAFETY_STATE_PATH": str(safety),
        "PAPER_TRADING": "true",
        "EXECUTION_MODE": "paper",
        "TRADING_MODE": "practice",
        "USE_OANDA_LIVE": "false",
        "TELEGRAM_COMMANDS": "0",
        "TELEGRAM_INBOUND": "0",
        "OANDA_ACCESS_TOKEN": "",
        "OANDA_API_KEY": "",
        "OANDA_ACCOUNT_ID": "",
        "TELEGRAM_TOKEN": "",
        "TELEGRAM_BOT_TOKEN": "",
        "DISCORD_WEBHOOK": "",
        "POSTGRES_HOST": "d5-invalid-host",
        "POSTGRES_PORT": "1",
        "POSTGRES_USER": "d5",
        "POSTGRES_PASSWORD": "",
        "POSTGRES_PASS": "",
        "POSTGRES_DB": "d5",
    }
    completed = subprocess.run(
        [sys.executable, str(RUNNER), str(out)],
        cwd=str(work),
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    payload["_returncode"] = completed.returncode
    payload["_stderr_tail"] = completed.stderr[-2000:]
    return payload


def test_runner_completed_without_guard_trip(report: dict) -> None:
    assert report.get("error", "") == ""
    assert report["_returncode"] == 0
    assert report["isolation_ok"] is True
    assert report["foreign_project_on_path"] is False
    assert report["dotenv_calls_at_import"] >= 1
    assert report["entrypoint"] == "async with forex_bot.app.lifespan(app)"


def test_t01_t02_t03_valid_blocked_startup(report: dict) -> None:
    case = _case(report, "valid_blocked")
    assert case["aborted"] is False
    assert case["counts"]["yielded"] == 1
    assert case["auth"] == "BLOCKED"
    assert case["initialised"] is True
    assert case["active"] == []
    assert case["counts"]["get_connection"] == 1
    assert case["counts"]["build_api"] == 1
    assert case["counts"]["fetch_account_summary"] == 1
    assert case["counts"]["run_reconciliation_once"] == 1
    assert case["counts"]["create_task"] == 4
    assert case["counts"]["stop_telegram_control"] == 1
    assert case["network"] == []


def test_t02_persisted_allowed_stays_blocked(report: dict) -> None:
    case = _case(report, "valid_persisted_allowed")
    assert case["aborted"] is False
    assert case["auth"] == "BLOCKED"
    assert case["active"] == []
    assert case["initialised"] is True


def test_t04_t05_corrupt_aborts_and_preserves(report: dict) -> None:
    case = _case(report, "corrupt")
    assert case["aborted"] is True
    assert case["abort_type"] == "StartupSafetyAbort"
    assert "corrupt_or_unreadable_state" in case["message"]
    assert case["bytes_unchanged"] is True
    _zero_downstream(case)


def test_t06_t07_future_schema_aborts_and_preserves(report: dict) -> None:
    case = _case(report, "future")
    assert case["aborted"] is True
    assert "unsupported_future_schema" in case["message"]
    assert case["bytes_unchanged"] is True
    assert "synthetic-marker" not in case["message"]
    _zero_downstream(case)


def test_t08_t09_t33_invalid_activation_aborts(report: dict) -> None:
    case = _case(report, "invalid")
    assert case["aborted"] is True
    assert "corrupt_or_unreadable_state" in case["message"]
    assert case["bytes_unchanged"] is True
    assert case["active"] == []
    _zero_downstream(case)


def test_t10_t11_unreadable_and_permission_are_not_missing(report: dict) -> None:
    unreadable = _case(report, "unreadable")
    permission = _case(report, "permission")
    assert unreadable["aborted"] is True
    assert "safety_state_unreadable" in unreadable["message"]
    assert unreadable["bytes_unchanged"] is True
    assert permission["aborted"] is True
    assert "safety_state_unreadable" in permission["message"]
    assert "default_deny_no_durable_state" not in permission["message"]
    assert permission["bytes_unchanged"] is True
    _zero_downstream(unreadable)
    _zero_downstream(permission)


def test_t12_t13_missing_file_initialises_inactive(report: dict) -> None:
    case = _case(report, "missing")
    assert case["aborted"] is False
    assert case["existed_before"] is False
    assert case["exists_after"] is True
    assert case["auth"] == "BLOCKED"
    assert case["active"] == []
    assert case["initialised"] is True


def test_t14_t15_failed_write_aborts_before_services(report: dict) -> None:
    case = _case(report, "replace_fail")
    assert case["aborted"] is True
    assert "persistence_failure" in case["message"]
    assert case["bytes_unchanged"] is True
    _zero_downstream(case)


def test_t16_through_t26_protected_has_no_downstream(report: dict) -> None:
    for name in ("corrupt", "future", "invalid", "unreadable", "permission"):
        case = _case(report, name)
        assert case["abort_type"] == "StartupSafetyAbort"
        _zero_downstream(case)


def test_t27_t28_t29_valid_order_and_shutdown(report: dict) -> None:
    case = _case(report, "valid_blocked")
    events = case["events"]
    assert events.index("get_connection") < events.index("build_api")
    assert events.index("build_api") < events.index("fetch_account_summary")
    assert events.index("fetch_account_summary") < events.index("run_reconciliation_once")
    assert events.index("run_reconciliation_once") < events.index("create_task")
    assert events.index("yielded") < events.index("stop_telegram_control")
    scheduled = [item for item in events if item.startswith("scheduled:")]
    assert scheduled == ["scheduled:_inner", "scheduled:_inner", "scheduled:_inner", "scheduled:_inner"]
    assert "scheduled:health_snapshot_loop" not in events
    assert "scheduled:run_bot" not in events
    assert case["counts"]["stop_telegram_control"] == 1


def test_t30_repeated_protected_startup_preserves_bytes(report: dict) -> None:
    second = _case(report, "repeat_second")
    assert second["aborted"] is True
    assert second["bytes_unchanged"] is True
    assert second["initialised_before"] is False
    _zero_downstream(second)


def test_t31_t32_success_then_corrupt_still_aborts(report: dict) -> None:
    first = _case(report, "stale_success")
    second = _case(report, "stale_then_corrupt")
    assert first["aborted"] is False
    assert first["initialised"] is True
    assert second["initialised_before"] is True
    assert second["aborted"] is True
    assert second["initialised"] is False
    assert second["bytes_unchanged"] is True
    _zero_downstream(second)


def test_t34_protected_does_not_continue(report: dict) -> None:
    case = _case(report, "future")
    assert case["counts"].get("yielded", 0) == 0
    assert case["aborted"] is True


def test_t35_through_t47_no_real_services(report: dict) -> None:
    for case in report["cases"].values():
        assert case["network"] == []
        assert case["fs_denials"] == []
        assert case["counts"].get("requests", 0) == 0
        assert case["counts"].get("psycopg2.connect", 0) == 0
        assert case["auth"] == "BLOCKED"
        assert not any(str(key).startswith("order_route:") for key in case["counts"])

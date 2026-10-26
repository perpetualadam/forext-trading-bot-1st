"""Stage D.7 resource cleanup. This module does not import app.py."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = Path(__file__).resolve().parent / "d7_resource_cleanup_runner.py"
D5_RUNNER = Path(__file__).resolve().parent / "d5_lifespan_runner.py"
SIX = [
    "mean_reversion",
    "scalp",
    "swing_breakout",
    "swing_mean_reversion",
    "swing_trend",
    "trend",
]
UNCHANGED = {
    "forex_bot/live_safety.py": (
        "11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44"
    ),
    "forex_bot/strategy_meta.py": (
        "492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d"
    ),
    "tests/d5_lifespan_runner.py": (
        "0729bea1df8a59d5dde3c66c396a476a0abb80c9c36213f15f08fcb77f2a3b60"
    ),
    "tests/test_d5_lifespan_isolation.py": (
        "8cf8c712979ad32eac648b4a8f18d65546bf24a72d2a4e6f4f3ff6041bd88dd4"
    ),
    "tests/d6_partial_startup_runner.py": (
        "0f26f2f9de022e47d0a1865f06f2be217c6d903bceb6031c1dc8aa3348734336"
    ),
    "tests/test_d6_partial_startup_cleanup.py": (
        "1fd9c54a98da7f099cfa8b204f234d22f7f61ca7cb5d315db9ce6e8c25498ad9"
    ),
}
PRE_D7_APP = "f38c304c4692c4a69e537610173e5691c03d49e24c48d6e258f56d1be75ae7b4"
PRE_D7_DATABASE = "98ed215c0a7e7f21ecf938172a45805a3f1b456c5cf49e8d0a8ea9f0d5cbce72"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _child_env(work: Path, safety: Path) -> dict[str, str]:
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
    return {
        **inherited,
        "PYTHONPATH": str(ROOT),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_CURRENT_TEST": "d7-isolated",
        "LIVE_SAFETY_STATE_PATH": str(safety),
        "D7_WORK_DIR": str(work),
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
        "DISCORD_WEBHOOK_URL": "",
        "POSTGRES_HOST": "d7-invalid-host",
        "POSTGRES_PORT": "1",
        "POSTGRES_USER": "d7",
        "POSTGRES_PASSWORD": "",
        "POSTGRES_PASS": "",
        "POSTGRES_DB": "d7",
    }


def _run(tmp_path_factory: pytest.TempPathFactory, mode: str) -> dict:
    for rel, digest in UNCHANGED.items():
        assert _sha(ROOT / rel) == digest
    assert _sha(ROOT / "forex_bot/app.py") != PRE_D7_APP
    assert _sha(ROOT / "forex_bot/database.py") != PRE_D7_DATABASE
    work = tmp_path_factory.mktemp(f"d7-{mode}")
    out = work / "report.json"
    completed = subprocess.run(
        [sys.executable, str(RUNNER), str(out), mode],
        cwd=str(work),
        env=_child_env(work, work / "safety.json"),
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    payload["_returncode"] = completed.returncode
    payload["_stderr_tail"] = completed.stderr[-1500:]
    return payload


def _case(report: dict, name: str) -> dict:
    return report["cases"][name]


def _conn(case: dict) -> dict:
    assert len(case["connections"]) == 1
    return case["connections"][0]


def _blocked(case: dict) -> None:
    assert case["auth"] == "BLOCKED"
    assert case["active"] == []
    assert case["strategy_names"] == SIX
    assert case["network"] == []
    assert case["fs_denials"] == []
    assert case["order_routes"] == []


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = _run(tmp_path_factory, "lifespan")
    assert payload.get("error", "") == "", payload.get(
        "traceback", payload.get("error")
    )
    assert payload["_returncode"] == 0
    return payload


@pytest.fixture(scope="module")
def database_report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = _run(tmp_path_factory, "database")
    assert payload.get("error", "") == "", payload.get(
        "traceback", payload.get("error")
    )
    assert payload["_returncode"] == 0
    return payload


@pytest.fixture(scope="module")
def repair_report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    return _run(tmp_path_factory, "repair")


def test_t01_t03_protected_state_aborts_before_resources(report: dict) -> None:
    source = (ROOT / "forex_bot/app.py").read_text(encoding="utf-8")
    lifespan = source.split("async def lifespan", 1)[1].split("\napp = FastAPI", 1)[0]
    abort = lifespan.index("raise StartupSafetyAbort")
    assert "except StartupSafetyAbort" not in source
    for fragment in (
        "get_connection()",
        "build_api()",
        "create_task(reconciliation_loop())",
        "create_task(health_snapshot_loop())",
        "create_task(telegram_inbound_loop())",
        "create_task(run_bot())",
    ):
        assert abort < lifespan.index(fragment)
    for name in ("corrupt", "future", "invalid"):
        case = _case(report, name)
        assert case["yielded"] is False
        assert case["escaped_type"] == "StartupSafetyAbort"
        assert case["counts"].get("psycopg2.connect", 0) == 0
        assert case["counts"].get("build_api", 0) == 0
        assert case["tasks_created"] == 0
        assert case["connections"] == []
        _blocked(case)


def test_t04_t06_valid_blocked_stays_inactive(report: dict) -> None:
    case = _case(report, "baseline")
    assert case["yielded"] is True
    assert case["escaped_type"] == ""
    assert case["file_auth"] == "BLOCKED"
    _blocked(case)
    assert case["counts"].get("get_connection", 0) == 0
    assert report["get_connection_is_real"] is True


def test_t07_connect_failure_keeps_public_contract(
    report: dict, database_report: dict
) -> None:
    case = _case(report, "db_connect")
    row = database_report["scenarios"]["connect_failure"]
    assert case["yielded"] is True
    assert case["escaped_type"] == ""
    assert case["connections"] == []
    assert case["pg_conn_held"] is False
    assert row["returned_none"] is True
    assert row["connections"] == []
    assert row["connect_calls"] == 1
    _blocked(case)


def test_t08_t11_cursor_and_execute_failures_release_new_resources(
    database_report: dict,
) -> None:
    cursor = database_report["scenarios"]["cursor_failure"]
    execute = database_report["scenarios"]["execute_failure"]
    cursor_row = cursor["connections"][0]
    execute_row = execute["connections"][0]
    assert cursor["returned_none"] is True
    assert cursor["pg_conn_is_none"] is True
    assert cursor["unrelated_close_calls"] == 0
    assert cursor_row["close_calls"] == 1
    assert cursor_row["closed"] is True
    assert cursor_row["rollbacks"] == 1
    assert cursor_row["cursor_created"] is False
    assert execute["returned_none"] is True
    assert execute_row["cursor_created"] is True
    assert execute_row["cursor_closed"] is True
    assert execute_row["rollbacks"] == 1
    assert execute_row["closed"] is True
    assert execute_row["close_calls"] == 1
    assert execute["partial_cleanup_errors"] == []


def test_t12_t17_commit_and_cleanup_errors_do_not_mask_failure(
    database_report: dict,
) -> None:
    commit = database_report["scenarios"]["commit_failure"]["connections"][0]
    rollback = database_report["scenarios"]["rollback_failure"]
    cursor_close = database_report["scenarios"]["cursor_close_failure"]
    conn_close = database_report["scenarios"]["connection_close_failure"]
    assert commit["rollbacks"] == 1
    assert commit["cursor_closed"] is True
    assert commit["closed"] is True
    assert commit["close_calls"] == 1
    assert rollback["returned_none"] is True
    assert rollback["pg_conn_is_none"] is True
    assert "RuntimeError" in rollback["partial_cleanup_errors"]
    assert rollback["connections"][0]["closed"] is True
    assert cursor_close["returned_none"] is True
    assert cursor_close["connections"][0]["closed"] is True
    assert "RuntimeError" in cursor_close["partial_cleanup_errors"]
    assert conn_close["returned_none"] is True
    assert conn_close["pg_conn_is_none"] is True
    assert conn_close["connections"][0]["close_calls"] == 1
    assert "RuntimeError" in conn_close["partial_cleanup_errors"]


def test_t15_t16_t18_failed_initialization_does_not_reuse_or_close_healthy(
    database_report: dict,
) -> None:
    retry = database_report["scenarios"]["retry_after_failure"]
    healthy = database_report["scenarios"]["healthy_not_reinitialized"]
    assert retry["first_none"] is True
    assert retry["failed_closed"] is True
    assert retry["second_is_new"] is True
    assert retry["second_closed"] is False
    assert retry["published_is_second"] is True
    assert retry["connect_calls"] == 2
    assert healthy["same_object"] is True
    assert healthy["healthy_close_calls"] == 0
    assert healthy["connect_calls"] == 0


def test_t19_t20_release_is_idempotent_and_does_not_connect(
    database_report: dict,
) -> None:
    row = database_report["scenarios"]["release_idempotent"]
    assert row["close_calls"] == 1
    assert row["published_closed"] is True
    assert row["pg_conn_is_none"] is True
    assert row["first_notes"] == []
    assert row["second_notes"] == []
    assert row["connect_calls_before"] == row["connect_calls_after"] == 1
    assert row["other_close_calls"] == 0


def test_t21_t22_t32_fatal_pre_yield_releases_connection_and_tasks(
    report: dict,
) -> None:
    for name in ("broker", "before_tasks"):
        case = _case(report, name)
        row = _conn(case)
        assert case["yielded"] is False
        assert case["escaped_type"] == "RuntimeError"
        assert case["tasks_pending_after_application"] == 0
        assert case["harness_cancelled"] == 0
        assert case["harness_closed_connections"] == 0
        assert case["pg_conn_held"] is False
        assert row["close_calls"] == 1
        assert row["closed"] is True
        assert row["pending_at_close"] == 0
        _blocked(case)


def test_t23_t26_t30_task_creation_failures_cancel_earlier_tasks(report: dict) -> None:
    first = _case(report, "after_first")
    later = _case(report, "later_task")
    before = _case(report, "before_yield")
    assert first["tasks_created"] == 1
    assert first["tasks_pending_after_application"] == 0
    assert first["tasks_cancelled_by_application"] == 1
    assert first["harness_cancelled"] == 0
    assert later["tasks_created"] == 3
    assert later["tasks_pending_after_application"] == 0
    assert later["tasks_cancelled_by_application"] == 3
    assert before["tasks_created"] == 4
    assert before["tasks_done_after_application"] == 4
    assert before["tasks_pending_after_application"] == 0
    assert before["harness_cancelled"] == 0
    for case in (first, later, before):
        assert case["yielded"] is False
        assert case["pg_conn_held"] is False
        assert _conn(case)["pending_at_close"] == 0
        assert _conn(case)["close_calls"] == 1
        assert case["harness_closed_connections"] == 0
        _blocked(case)


def test_t27_t29_t31_shutdown_failures_still_clean_every_task(report: dict) -> None:
    stop = _case(report, "shutdown_stop")
    health = _case(report, "await_health")
    other = _case(report, "await_reco")
    for case in (stop, health, other):
        assert case["yielded"] is True
        assert case["escaped_type"] == "RuntimeError"
        assert case["tasks_created"] == 4
        assert case["tasks_pending_after_application"] == 0
        assert case["tasks_done_after_application"] == 4
        assert case["harness_cancelled"] == 0
        assert "RuntimeError" in case["cleanup_errors"]
        assert case["pg_conn_held"] is True
        _blocked(case)
    assert "injected shutdown failure" in stop["message"]
    assert "injected task await failure" in health["message"]
    assert "injected other task await failure" in other["message"]
    assert stop["tasks_cancelled_by_application"] == 4
    assert health["tasks_cancelled_by_application"] == 3
    assert other["tasks_cancelled_by_application"] == 3


def test_t33_t35_t55_t64_t65_normal_shutdown_and_single_release(report: dict) -> None:
    case = _case(report, "baseline")
    row = _conn(case)
    assert case["tasks_created"] == 4
    assert case["tasks_cancelled_by_application"] == 4
    assert case["tasks_pending_after_application"] == 0
    assert case["harness_cancelled"] == 0
    assert case["cleanup_errors"] == []
    assert case["pg_conn_held"] is True
    assert row["close_calls"] == 0
    assert case["harness_closed_connections"] == 1
    broker = _conn(_case(report, "broker"))
    assert broker["close_calls"] == 1
    assert broker["pending_at_close"] == 0


def test_t36_t39_primary_failure_stays_visible_without_authorising(
    report: dict,
) -> None:
    broker = _case(report, "broker")
    close_fail = _case(report, "broker_close")
    assert broker["message"] == "injected broker construction failure"
    assert broker["cleanup_errors"] == []
    assert "injected broker construction failure" in close_fail["message"]
    assert "RuntimeError" in close_fail["cleanup_errors"]
    assert "injected connection close failure" not in close_fail["message"]
    assert close_fail["pg_conn_held"] is False
    assert close_fail["auth"] == "BLOCKED"
    assert close_fail["active"] == []
    _blocked(broker)
    _blocked(close_fail)


def test_t40_t54_isolation_and_application_cleanup_observed_first(report: dict) -> None:
    checks = report["guard_checks"]
    assert checks == {
        "localhost_connect_denied": True,
        "external_connect_denied": True,
        "dns_denied": True,
        "self_pipe_port_not_reusable": True,
        "open_ops_denied": True,
        "open_env_denied": True,
        "open_credential_denied": True,
        "open_shadow_denied": True,
        "replace_ops_denied": True,
        "probe_denials_only": True,
    }
    assert report["foreign_project_on_path"] is False
    assert report["dotenv_calls_at_import"] >= 1
    assert report["network"] == []
    assert report["fs_denials"] == []
    assert report["self_pipe_count"] >= 1
    for case in report["cases"].values():
        assert case["network"] == []
        assert case["counts"].get("requests", 0) == 0
        assert set(case["scheduled"]) <= {"scheduled:_inner"}
        leaked = case["tasks_pending_after_application"]
        assert leaked == 0 or case["harness_cancelled"] == leaked
        fatal = {"broker", "before_tasks", "after_first", "later_task", "before_yield"}
        if case["inject"] in fatal:
            assert case["harness_closed_connections"] == 0
            assert _conn(case)["close_calls"] >= 1


def test_t62_t63_nonfatal_account_and_reconciliation_still_continue(
    report: dict,
) -> None:
    for name in ("account", "reconcile"):
        case = _case(report, name)
        assert case["yielded"] is True
        assert case["escaped_type"] == ""
        assert case["tasks_pending_after_application"] == 0
        assert case["tasks_cancelled_by_application"] == 4
        assert case["pg_conn_held"] is True
        assert _conn(case)["close_calls"] == 0
        _blocked(case)


def test_t08_lifespan_database_failures_continue_without_a_held_connection(
    report: dict,
) -> None:
    for name, rollbacks, cursor_closed in (
        ("db_cursor", 1, False),
        ("db_execute", 1, True),
        ("db_commit", 1, True),
    ):
        case = _case(report, name)
        row = _conn(case)
        assert case["yielded"] is True
        assert case["escaped_type"] == ""
        assert case["pg_conn_held"] is False
        assert row["close_calls"] == 1
        assert row["closed"] is True
        assert row["rollbacks"] == rollbacks
        assert row["cursor_closed"] is cursor_closed
        assert case["tasks_pending_after_application"] == 0
        assert case["harness_closed_connections"] == 0
        _blocked(case)
    rollback = _case(report, "db_rollback")
    assert rollback["yielded"] is True
    assert rollback["escaped_type"] == ""
    assert "RuntimeError" in rollback["partial_cleanup_errors"]
    assert _conn(rollback)["closed"] is True


def test_repeat_startup_after_cleaned_failure_stays_blocked(report: dict) -> None:
    first = _case(report, "repeat_first")
    second = _case(report, "repeat_second")
    assert first["tasks_pending_after_application"] == 0
    assert first["harness_cancelled"] == 0
    assert second["yielded"] is True
    assert second["file_auth"] == "BLOCKED"
    _blocked(second)


def test_t61_repair_module_passes_under_isolation(repair_report: dict) -> None:
    assert repair_report.get("error", "") == "", repair_report.get("traceback")
    assert repair_report["_returncode"] == 0
    assert repair_report["repair_exit_code"] == 0
    assert repair_report["network"] == []
    assert repair_report["get_connection_is_real"] is True


def test_t59_d5_runner_behavior_still_passes(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    for rel, digest in UNCHANGED.items():
        assert _sha(ROOT / rel) == digest
    work = tmp_path_factory.mktemp("d7-d5-replay")
    out = work / "d5.json"
    env = _child_env(work, work / "safety.json")
    completed = subprocess.run(
        [sys.executable, str(D5_RUNNER), str(out)],
        cwd=str(work),
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert completed.returncode == 0, payload.get("traceback", completed.stderr[-1500:])
    assert payload.get("error", "") == ""
    valid = payload["cases"]["valid_blocked"]
    corrupt = payload["cases"]["corrupt"]
    assert valid["aborted"] is False
    assert "yielded" in valid["events"]
    assert valid["auth"] == "BLOCKED"
    assert valid["active"] == []
    assert valid["network"] == []
    assert corrupt["aborted"] is True
    assert corrupt["abort_type"] == "StartupSafetyAbort"
    assert corrupt["counts"].get("get_connection", 0) == 0
    assert corrupt["counts"].get("build_api", 0) == 0

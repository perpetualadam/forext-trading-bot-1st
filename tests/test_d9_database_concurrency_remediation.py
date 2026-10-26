"""Stage D.9 post-fix checks. This module does not import app.py."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = Path(__file__).resolve().parent / "d9_database_concurrency_runner.py"
UNCHANGED = {
    "forex_bot/app.py": (
        "08766300dfaf703e7553c69703e5d5f2c90e8efc2b491e6eeff1791ca93e3b44"
    ),
    "forex_bot/live_safety.py": (
        "11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44"
    ),
    "forex_bot/strategy_meta.py": (
        "492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d"
    ),
}
PRE_D9_DATABASE = "74bb9f5d692ace88bff525f334d7eb8577427bfe75cf5f229f647e60b88979e9"


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
        "PYTEST_CURRENT_TEST": "d9-isolated",
        "LIVE_SAFETY_STATE_PATH": str(safety),
        "D9_WORK_DIR": str(work),
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
        "POSTGRES_HOST": "d9-invalid-host",
        "POSTGRES_PORT": "1",
        "POSTGRES_USER": "d9",
        "POSTGRES_PASSWORD": "",
        "POSTGRES_PASS": "",
        "POSTGRES_DB": "d9",
    }


def _run(tmp_path_factory: pytest.TempPathFactory, mode: str) -> dict:
    for rel, digest in UNCHANGED.items():
        assert _sha(ROOT / rel) == digest
    assert _sha(ROOT / "forex_bot/database.py") != PRE_D9_DATABASE
    work = tmp_path_factory.mktemp(f"d9-{mode}")
    out = work / "report.json"
    completed = subprocess.run(
        [sys.executable, str(RUNNER), str(out), mode],
        cwd=str(work),
        env=_child_env(work, work / "safety.json"),
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    payload["_returncode"] = completed.returncode
    payload["_stderr_tail"] = completed.stderr[-1500:]
    return payload


def _sched(report: dict, name: str) -> dict:
    return report["schedules"][name]


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = _run(tmp_path_factory, "concurrency")
    assert payload.get("error", "") == "", payload.get(
        "traceback", payload.get("error")
    )
    assert payload["_returncode"] == 0
    return payload


@pytest.fixture(scope="module")
def lifespan_report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    payload = _run(tmp_path_factory, "lifespan")
    assert payload.get("error", "") == "", payload.get(
        "traceback", payload.get("error")
    )
    assert payload["_returncode"] == 0
    return payload


def test_lock_and_isolation(report: dict) -> None:
    source = (ROOT / "forex_bot/database.py").read_text(encoding="utf-8")
    start = source.index("def get_connection(")
    end = source.index("\ndef log_trade_pg(")
    body = source[start:end]
    assert "with _pg_lock:" in body
    assert body.index("with _pg_lock:") < body.index("psycopg2.connect(")
    assert body.index("psycopg2.connect(") < body.index("_pg_conn = new_conn")
    assert body.index("_pg_conn = new_conn") < body.index("_pg_cursor = new_cursor")
    assert report["lock"]["reentrant"] is True
    assert report["lock"]["get_connection_module"] == "forex_bot.database"
    assert report["foreign_project_on_path"] is False
    assert report["network"] == []
    guards = report["guard_checks"]
    for name in (
        "localhost_denied",
        "connect_ex_denied",
        "create_connection_denied",
        "dns_denied",
        "gethostbyname_denied",
        "urlopen_denied",
        "open_connection_denied",
        "start_server_denied",
        "subprocess_exec_denied",
        "subprocess_shell_denied",
        "system_denied",
        "popen_denied",
        "self_pipe_not_reusable",
        "ops_denied",
        "shadow_denied",
        "credential_denied",
        "env_denied",
        "volume_denied",
        "path_open_denied",
    ):
        assert guards[name] is True, name


def test_overlapping_callers_publish_one_connection(report: dict) -> None:
    row = _sched(report, "serialized_overlap")
    assert row["second_blocked_while_first_connected"] is True
    assert row["connects_while_held"] == 1
    assert row["connect_calls"] == 1
    assert row["cursors_created"] == 1
    assert row["abandoned_open"] == 0
    assert row["pair_consistent"] is True
    assert row["published_open"] is True
    assert row["application_closed"] == 0
    assert row["harness_closed"] == 1
    assert row["worker_errors"] == []
    assert row["returned_ids"] == [row["published_id"], row["published_id"]]


def test_failures_then_retry(report: dict) -> None:
    for name in ("cursor_fails", "sql_fails", "commit_fails"):
        row = _sched(report, name)
        assert row["first_none"] is True, name
        assert row["published_is_second"] is True, name
        assert row["abandoned_open"] == 0, name
        assert row["pair_consistent"] is True, name
        assert row["connect_calls"] == 2, name
        assert row["partial_notes"] == [], name
        assert row["notes_after_first"] == [], name
    rollback = _sched(report, "rollback_fails")
    assert rollback["first_none"] is True
    assert rollback["published_is_second"] is True
    assert "RuntimeError" in rollback["notes_after_first"]
    assert rollback["abandoned_open"] == 0
    cursor_close = _sched(report, "cursor_close_fails")
    assert "RuntimeError" in cursor_close["notes_after_first"]
    assert cursor_close["published_is_second"] is True
    assert cursor_close["abandoned_open"] == 0
    conn_close = _sched(report, "conn_close_fails")
    assert "RuntimeError" in conn_close["notes_after_first"]
    assert conn_close["published_is_second"] is True
    assert conn_close["abandoned_open"] == 0
    assert conn_close["harness_closed"] == 2


def test_both_fail_and_healthy_global_survives(report: dict) -> None:
    both = _sched(report, "both_fail")
    assert both["first_none"] is True
    assert both["second_none"] is True
    assert both["published_id"] is None
    assert both["abandoned_open"] == 0
    assert both["application_closed"] == 2
    assert both["harness_closed"] == 0
    healthy = _sched(report, "failed_cleanup_keeps_healthy")
    assert healthy["failed_none"] is True
    assert healthy["global_still_healthy"] is True
    assert healthy["abandoned_open"] == 0


def test_release_replace_and_nested_helper(report: dict) -> None:
    release = _sched(report, "release")
    replaced = _sched(report, "replace_during_close")
    nested = _sched(report, "nested_helper")
    waiting = _sched(report, "nested_waits")
    assert release["borrowed_closed"] is True
    assert release["second_release_notes"] == []
    assert release["release_created_connection"] is False
    assert release["harness_closed"] == 0
    assert replaced["old_closed"] is True
    assert replaced["new_open"] is True
    assert replaced["published_id"] == replaced["new_id"]
    assert replaced["published_id"] != replaced["old_id"]
    assert nested["helper_rows"] == []
    assert nested["second_helper_rows"] == []
    assert nested["connects_after_second_helper"] == 1
    assert nested["abandoned_open"] == 0
    assert waiting["helper_blocked"] is True
    assert waiting["connects_while_held"] == 1
    assert waiting["connect_calls"] == 1
    assert waiting["abandoned_open"] == 0
    assert waiting["worker_errors"] == []
    for row in report["schedules"].values():
        assert row["requests"] == 0
        assert row["network"] == []
        assert row["alive_workers"] == 0


def test_lifespan_preserves_cleanup_rules(lifespan_report: dict) -> None:
    cases = lifespan_report["cases"]
    corrupt = cases["corrupt"]
    baseline = cases["baseline"]
    broker = cases["broker"]
    stop = cases["shutdown_stop"]
    health = cases["await_health"]
    before = cases["before_yield"]
    startup_stop = cases["startup_stop"]
    repeat = cases["repeat"]
    assert corrupt["yielded"] is False
    assert corrupt["escaped_type"] == "StartupSafetyAbort"
    assert corrupt["connect_calls"] == 0
    assert corrupt["created"] == 0
    assert baseline["yielded"] is True
    assert baseline["auth"] == "BLOCKED"
    assert baseline["active"] == []
    assert baseline["pending"] == 0
    assert baseline["created"] == 4
    assert baseline["pg_conn_held"] is True
    assert baseline["application_closed"] == 0
    assert baseline["harness_closed"] == 1
    assert broker["pg_conn_held"] is False
    assert broker["application_closed"] >= 1
    assert broker["harness_closed"] == 0
    assert broker["pending"] == 0
    assert stop["pending"] == 0
    assert stop["harness_cancelled"] == 0
    assert stop["pg_conn_held"] is True
    assert "RuntimeError" in stop["cleanup_errors"]
    assert health["pending"] == 0
    assert health["harness_cancelled"] == 0
    assert "injected task await failure" in health["message"]
    assert before["pending"] == 0
    assert before["pg_conn_held"] is False
    assert before["harness_cancelled"] == 0
    assert startup_stop["yielded"] is False
    assert startup_stop["pending"] == 0
    assert startup_stop["pg_conn_held"] is True
    assert startup_stop["application_closed"] == 0
    assert "RuntimeError" in startup_stop["cleanup_errors"]
    assert "injected failure before yield" in startup_stop["message"]
    assert repeat["yielded"] is True
    assert repeat["auth"] == "BLOCKED"
    assert repeat["active"] == []
    assert repeat["pending"] == 0
    for case in cases.values():
        assert case["requests"] == 0
    assert lifespan_report["network"] == []

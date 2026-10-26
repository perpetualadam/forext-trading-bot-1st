"""Isolated R.62 proof-of-concept tests. No trading imports and no sockets."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
WINDOWS = sys.platform == "win32"


def _owner(kind: str, directory: Path, result: Path) -> subprocess.CompletedProcess[bytes]:
    directory.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [sys.executable, "-B", str(HERE / "owner_crash.py"), kind, str(result), str(directory)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = proc.communicate(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)
    return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)


def _kill_pid(pid: int) -> None:
    if pid <= 0:
        return
    if WINDOWS:
        from win_containment import _KERNEL, _wait_dead

        handle = _KERNEL.OpenProcess(0x0001, False, pid)
        if handle:
            _KERNEL.TerminateProcess(handle, 1)
            _wait_dead(handle, 3000)
            _KERNEL.CloseHandle(handle)
        return
    import os
    import signal

    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


@pytest.mark.skipif(not WINDOWS, reason="Windows job object")
def test_deadline_before_create_starts_nothing(tmp_path: Path) -> None:
    from win_containment import launch

    session = launch("side", time.monotonic() - 1, tmp_path)
    try:
        assert session.state == "NOT_STARTED"
        assert session.error == "DEADLINE_BEFORE_CREATE"
        assert session.pid == 0
        assert not (tmp_path / "side.txt").exists()
    finally:
        session.close()


@pytest.mark.skipif(not WINDOWS, reason="Windows job object")
def test_deadline_before_resume_does_not_run_worker_code(tmp_path: Path) -> None:
    from win_containment import launch, pid_active

    def _late(_pid: int) -> None:
        time.sleep(0.45)

    session = launch("side", time.monotonic() + 0.2, tmp_path, after_create=_late)
    try:
        assert session.error == "DEADLINE_BEFORE_RESUME"
        assert session.exit_verified is True
        assert session.side_effect_written is False
        assert not pid_active(session.pid)
        assert not (tmp_path / "side.txt").exists()
    finally:
        session.close()
        assert session.harness_intervened is False


@pytest.mark.skipif(not WINDOWS, reason="Windows job object")
def test_failed_assignment_does_not_resume(tmp_path: Path) -> None:
    from win_containment import launch, pid_active

    session = launch("side", time.monotonic() + 5, tmp_path, fail_job=True)
    try:
        assert session.error == "CONTAINMENT_FAILED"
        assert session.contained is False
        assert session.exit_verified is True
        assert session.side_effect_written is False
        assert not pid_active(session.pid)
    finally:
        session.close()


@pytest.mark.skipif(not WINDOWS, reason="Windows job object")
def test_job_close_kills_grandchild(tmp_path: Path) -> None:
    from win_containment import launch, pid_active

    session = launch("grand", time.monotonic() + 5, tmp_path)
    try:
        assert session.state == "WORKER_READY"
        assert session.contained is True
        assert session.descendant_pid > 0
        state = session.shutdown()
        assert state == "EXIT_VERIFIED"
        assert session.exit_verified is True
        assert not pid_active(session.pid)
        assert session.descendant_alive is False
        assert not pid_active(session.descendant_pid)
    finally:
        session.close()
        assert session.harness_intervened is False


@pytest.mark.skipif(not WINDOWS, reason="Windows job object")
def test_sigterm_handler_does_not_survive_job_close(tmp_path: Path) -> None:
    from win_containment import launch, pid_active

    session = launch("ignore", time.monotonic() + 5, tmp_path)
    try:
        assert session.state == "WORKER_READY"
        assert session.shutdown() == "EXIT_VERIFIED"
        assert not pid_active(session.pid)
    finally:
        session.close()


@pytest.mark.skipif(not WINDOWS, reason="Windows job object")
def test_exit_before_ready_is_verified(tmp_path: Path) -> None:
    from win_containment import launch

    session = launch("exit", time.monotonic() + 5, tmp_path)
    try:
        assert session.error == "EXIT_BEFORE_READY"
        assert session.ready is False
        assert session.exit_verified is True
    finally:
        session.close()


@pytest.mark.skipif(not WINDOWS, reason="Windows job object")
def test_duplicate_job_handle_keeps_the_worker_until_the_last_close(tmp_path: Path) -> None:
    from win_containment import launch, pid_active

    session = launch("ready", time.monotonic() + 5, tmp_path, keep_extra_job_handle=True)
    try:
        assert session.state == "WORKER_READY"
        assert session.shutdown() == "CLEANUP_INCOMPLETE"
        assert session.exit_verified is False
        assert pid_active(session.pid)
        session.close_extra_job_handle()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and pid_active(session.pid):
            time.sleep(0.05)
        assert not pid_active(session.pid)
    finally:
        session.close()


@pytest.mark.skipif(not WINDOWS, reason="Windows job object")
def test_ready_file_is_not_required_to_terminate(tmp_path: Path) -> None:
    from win_containment import launch, pid_active

    session = launch("ready", time.monotonic() + 5, tmp_path)
    try:
        assert session.ready is True
        assert session.shutdown() == "EXIT_VERIFIED"
        assert not pid_active(session.pid)
    finally:
        session.close()


@pytest.mark.skipif(not WINDOWS, reason="Windows job object")
def test_repeated_sessions_leave_no_worker(tmp_path: Path) -> None:
    from win_containment import launch, pid_active

    for index in range(3):
        folder = tmp_path / str(index)
        folder.mkdir()
        session = launch("side", time.monotonic() + 5, folder)
        try:
            assert session.ready is True
            assert session.shutdown() == "EXIT_VERIFIED"
            assert not pid_active(session.pid)
        finally:
            session.close()
            assert session.harness_intervened is False


@pytest.mark.skipif(not WINDOWS, reason="Windows job object")
def test_blocked_stdin_is_released_by_job_close_without_owner_close(tmp_path: Path) -> None:
    from win_containment import launch_pipe_check

    result = launch_pipe_check(tmp_path)
    assert result["stdin_closed_while_alive"] is False
    assert result["writer_finished"] is True
    assert result["exit_verified"] is True
    assert result["pid_active"] is False
    assert float(result["elapsed"]) < 4.0


@pytest.mark.skipif(not WINDOWS, reason="Windows job object")
def test_blocked_pre_create_hook_does_not_return_or_start_a_worker(tmp_path: Path) -> None:
    status = tmp_path / "status.txt"
    folder = tmp_path / "work"
    folder.mkdir()
    driver = tmp_path / "stall.py"
    driver.write_text(
        "import sys, time\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "import win_containment\n"
        "status = Path(sys.argv[2])\n"
        "folder = Path(sys.argv[3])\n"
        "def before():\n"
        "    status.write_text('entered', encoding='utf-8')\n"
        "    time.sleep(30)\n"
        "win_containment.launch('side', time.monotonic() + 0.2, folder, before_create=before)\n"
        "status.write_text('returned', encoding='utf-8')\n",
        encoding="utf-8",
    )
    proc = subprocess.Popen([sys.executable, "-B", str(driver), str(HERE), str(status), str(folder)])
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not status.is_file():
            if proc.poll() is not None:
                raise AssertionError("driver exited before the stall")
            time.sleep(0.05)
        assert status.read_text(encoding="utf-8") == "entered"
        time.sleep(0.5)
        assert proc.poll() is None
        assert not (folder / "side.txt").exists()
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)
    assert status.read_text(encoding="utf-8") == "entered"
    assert not (folder / "side.txt").exists()


@pytest.mark.skipif(not WINDOWS, reason="Windows job object")
def test_owner_exit_closes_the_job_and_the_grandchild(tmp_path: Path) -> None:
    from win_containment import pid_active

    result = tmp_path / "owner.json"
    folder = tmp_path / "work"
    completed = _owner("windows-contained", folder, result)
    payload = json.loads(result.read_text(encoding="utf-8"))
    grand = int((folder / "grand.txt").read_text(encoding="utf-8"))
    try:
        assert payload["contained"] is True
        assert payload["ready"] is True
        assert completed.returncode == 9
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and (pid_active(payload["pid"]) or pid_active(grand)):
            time.sleep(0.05)
        assert not pid_active(payload["pid"])
        assert not pid_active(grand)
    finally:
        if pid_active(payload["pid"]):
            _kill_pid(payload["pid"])
        if pid_active(grand):
            _kill_pid(grand)


@pytest.mark.skipif(WINDOWS, reason="Linux park and pidfd")
def test_cgroup_is_unavailable_and_not_reported_as_containment(tmp_path: Path) -> None:
    result = tmp_path / "cgroup.json"
    completed = _owner("linux-cgroup", tmp_path / "work", result)
    assert completed.returncode == 0
    payload = json.loads(result.read_text(encoding="utf-8"))
    assert payload["cgroup"].startswith("CONTAINMENT_UNAVAILABLE")


@pytest.mark.skipif(WINDOWS, reason="Linux park and pidfd")
def test_linux_deadline_before_exec_does_not_run_worker_code(tmp_path: Path) -> None:
    result = tmp_path / "result.json"
    folder = tmp_path / "work"
    completed = _owner("linux-before-resume", folder, result)
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")[-500:]
    payload = json.loads(result.read_text(encoding="utf-8"))
    assert payload["error"] == "DEADLINE_BEFORE_RESUME"
    assert payload["exit_verified"] is True
    assert payload["side"] is False
    assert payload["cgroup"].startswith("CONTAINMENT_UNAVAILABLE")
    assert not (folder / "side.txt").exists()


@pytest.mark.skipif(WINDOWS, reason="Linux park and pidfd")
def test_linux_owner_death_before_release_does_not_exec(tmp_path: Path) -> None:
    from linux_containment import pid_active

    result = tmp_path / "result.json"
    folder = tmp_path / "work"
    completed = _owner("linux-parked", folder, result)
    payload = json.loads(result.read_text(encoding="utf-8"))
    try:
        assert completed.returncode == 9
        assert payload["state"] == "WORKER_CREATED"
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and pid_active(payload["pid"]):
            time.sleep(0.05)
        assert not pid_active(payload["pid"])
        assert not (folder / "side.txt").exists()
    finally:
        if pid_active(payload["pid"]):
            _kill_pid(payload["pid"])


@pytest.mark.skipif(WINDOWS, reason="Linux park and pidfd")
def test_linux_grandchild_survives_owner_exit(tmp_path: Path) -> None:
    from linux_containment import pid_active

    result = tmp_path / "result.json"
    folder = tmp_path / "work"
    completed = _owner("linux-contained", folder, result)
    payload = json.loads(result.read_text(encoding="utf-8"))
    grand = int((folder / "grand.txt").read_text(encoding="utf-8"))
    try:
        assert completed.returncode == 9
        assert payload["contained"] is False
        assert payload["cgroup"].startswith("CONTAINMENT_UNAVAILABLE")
        assert payload["ready"] is True
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and pid_active(payload["pid"]):
            time.sleep(0.05)
        assert pid_active(payload["pid"]) is True
        assert pid_active(grand) is True
        assert payload["pid"] != grand
    finally:
        if pid_active(payload["pid"]):
            _kill_pid(payload["pid"])
        if pid_active(grand):
            _kill_pid(grand)


def test_poc_sources_do_not_touch_trading_or_credentials() -> None:
    banned = (
        "forex_bot",
        "oanda",
        "load_dotenv",
        "import requests",
        "import httpx",
        "diagnostic_supervisor",
        "live_session_gate",
        "one_session",
        ".env",
    )
    for path in HERE.glob("*.py"):
        if path.name == "test_contained_launch.py":
            continue
        text = path.read_text(encoding="utf-8").lower()
        for item in banned:
            assert item not in text

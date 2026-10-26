"""Windows creation-time job experiments. Skipped on other platforms."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows job assignment")
sys.path.insert(0, str(HERE))


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


def _kill(pid: int) -> None:
    import windows_backend

    handle = windows_backend._KERNEL.OpenProcess(0x0001, False, pid)
    if handle:
        windows_backend._KERNEL.TerminateProcess(handle, 1)
        windows_backend._wait_dead(handle, 3000)
        windows_backend._KERNEL.CloseHandle(handle)


def test_parent_is_already_in_a_job_and_creation_time_assignment_still_confirms(tmp_path: Path) -> None:
    import windows_backend
    from lifecycle_contract import DESCENDANT_CONTAINMENT_ACTIVE, ProcessLifecycleManager

    report = windows_backend.probe("REQUIRE_DESCENDANT_CONTAINMENT")
    assert report["parent_in_job"] is True
    assert report["actual_if_requested"] != DESCENDANT_CONTAINMENT_ACTIVE
    manager = ProcessLifecycleManager()
    session = manager.create_suspended_or_parked("side", time.monotonic() + 5, tmp_path)
    try:
        assert session.worker_executed is False
        assert not (tmp_path / "side.txt").exists()
        manager.establish_containment(session)
        assert session.actual_containment == DESCENDANT_CONTAINMENT_ACTIVE
        assert session.direct_child_ownership == "process-handle"
        active, _total = windows_backend.job_counts(session._native["job"])
        assert active >= 1
        manager.terminate(session, "STOP")
        assert session.exit_verified is False
        manager.verify_exit(session)
        assert session.exit_verified is True
        assert session.exit_verification == "EXIT_VERIFIED"
        assert not (tmp_path / "side.txt").exists()
    finally:
        manager.cleanup(session)


def test_deadline_before_release_does_not_run_worker_code(tmp_path: Path) -> None:
    from lifecycle_contract import ProcessLifecycleManager

    def _late(_pid: int) -> None:
        time.sleep(0.45)

    manager = ProcessLifecycleManager()
    session = manager.run("side", time.monotonic() + 0.2, tmp_path, before_release=_late)
    try:
        assert session.error == "DEADLINE_BEFORE_RELEASE"
        assert session.exit_verified is True
        assert session.worker_executed is False
        assert not (tmp_path / "side.txt").exists()
    finally:
        manager.cleanup(session)
        assert session.harness_intervened is False


def test_rejected_attribute_fails_closed(tmp_path: Path) -> None:
    import windows_backend

    session = windows_backend.create_with_rejected_attribute(tmp_path)
    assert session.error == "CREATE_ATTRIBUTE_REJECTED"
    assert session.pid == 0
    assert session.state == "NOT_STARTED"
    assert not (tmp_path / "side.txt").exists()


def test_grandchild_is_inside_the_job_and_dies_on_last_close(tmp_path: Path) -> None:
    import windows_backend
    from lifecycle_contract import ProcessLifecycleManager

    manager = ProcessLifecycleManager()
    session = manager.run("grand", time.monotonic() + 5, tmp_path)
    try:
        assert session.ready is True
        assert session.descendant_pid > 0
        active, _total = windows_backend.job_counts(session._native["job"])
        assert active >= 2
        manager.terminate(session, "STOP")
        manager.verify_exit(session)
        assert session.exit_verified is True
        assert windows_backend.pid_active(session.pid) is False
        assert windows_backend.pid_active(session.descendant_pid) is False
    finally:
        manager.cleanup(session)
        assert session.harness_intervened is False


def test_duplicate_job_handle_leaves_cleanup_incomplete_until_the_last_close(tmp_path: Path) -> None:
    import windows_backend
    from lifecycle_contract import CLEANUP_INCOMPLETE, ProcessLifecycleManager

    manager = ProcessLifecycleManager()
    session = manager.run("ready", time.monotonic() + 5, tmp_path)
    try:
        windows_backend.keep_extra_job_handle(session)
        manager.terminate(session, "STOP")
        manager.verify_exit(session, 1.0)
        assert session.exit_verified is False
        assert session.state == CLEANUP_INCOMPLETE
        assert windows_backend.pid_active(session.pid) is True
        windows_backend.close_extra_job_handle(session)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and windows_backend.pid_active(session.pid):
            time.sleep(0.05)
        manager.verify_exit(session)
        assert session.exit_verified is True
    finally:
        manager.cleanup(session)


def test_sigterm_handler_and_exit_before_ready(tmp_path: Path) -> None:
    import windows_backend
    from lifecycle_contract import ProcessLifecycleManager

    manager = ProcessLifecycleManager()
    ignored = manager.run("ignore", time.monotonic() + 5, tmp_path)
    try:
        assert ignored.ready is True
        manager.terminate(ignored, "STOP")
        manager.verify_exit(ignored)
        assert ignored.exit_verified is True
        assert windows_backend.pid_active(ignored.pid) is False
    finally:
        manager.cleanup(ignored)
    exited = manager.run("exit", time.monotonic() + 5, tmp_path / "exit")
    try:
        assert exited.error == "EXIT_BEFORE_READY"
        assert exited.ready is False
        assert exited.exit_verified is True
    finally:
        manager.cleanup(exited)


def test_repeated_sessions_leave_no_worker(tmp_path: Path) -> None:
    import windows_backend
    from lifecycle_contract import ProcessLifecycleManager

    manager = ProcessLifecycleManager()
    for index in range(3):
        folder = tmp_path / str(index)
        session = manager.run("side", time.monotonic() + 5, folder)
        try:
            assert session.ready is True
            manager.terminate(session, "STOP")
            manager.verify_exit(session)
            assert session.exit_verified is True
            assert windows_backend.pid_active(session.pid) is False
        finally:
            manager.cleanup(session)
            assert session.harness_intervened is False


def test_blocked_stdin_is_released_by_job_close(tmp_path: Path) -> None:
    import windows_backend

    result = windows_backend.blocked_stdin_is_not_closed(tmp_path)
    assert result["stdin_closed_while_alive"] is False
    assert result["writer_finished"] is True
    assert result["exit_verified"] is True
    assert result["pid_active"] is False
    assert float(result["elapsed"]) < 4.0


def test_pre_create_hook_does_not_return_or_start_a_worker(tmp_path: Path) -> None:
    status = tmp_path / "status.txt"
    folder = tmp_path / "work"
    folder.mkdir()
    driver = tmp_path / "stall.py"
    driver.write_text(
        "import sys, time\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "from lifecycle_contract import ProcessLifecycleManager\n"
        "status = Path(sys.argv[2])\n"
        "folder = Path(sys.argv[3])\n"
        "def before():\n"
        "    status.write_text('entered', encoding='utf-8')\n"
        "    time.sleep(30)\n"
        "ProcessLifecycleManager().create_suspended_or_parked('side', time.monotonic()+0.2, folder, before_create=before)\n"
        "status.write_text('returned', encoding='utf-8')\n",
        encoding="utf-8",
    )
    proc = subprocess.Popen([sys.executable, "-B", str(driver), str(HERE), str(status), str(folder)])
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not status.is_file():
            if proc.poll() is not None:
                raise AssertionError(proc.stderr.read() if proc.stderr else "driver exited")
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


def test_owner_exit_after_creation_kills_the_suspended_worker(tmp_path: Path) -> None:
    import windows_backend

    result = tmp_path / "owner.json"
    folder = tmp_path / "work"
    completed = _owner("win-created-exit", folder, result)
    payload = json.loads(result.read_text(encoding="utf-8"))
    try:
        assert completed.returncode == 9
        assert payload["actual_containment"] == "DESCENDANT_CONTAINMENT_ACTIVE"
        assert payload["worker_executed"] is False
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and windows_backend.pid_active(payload["pid"]):
            time.sleep(0.05)
        assert windows_backend.pid_active(payload["pid"]) is False
        assert not (folder / "side.txt").exists()
    finally:
        if windows_backend.pid_active(payload["pid"]):
            _kill(payload["pid"])


def test_owner_exit_kills_running_worker_and_grandchild(tmp_path: Path) -> None:
    import windows_backend

    result = tmp_path / "owner.json"
    folder = tmp_path / "work"
    completed = _owner("win-running-exit", folder, result)
    payload = json.loads(result.read_text(encoding="utf-8"))
    try:
        assert completed.returncode == 9
        assert payload["ready"] is True
        assert payload["descendant_pid"] > 0
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and (
            windows_backend.pid_active(payload["pid"]) or windows_backend.pid_active(payload["descendant_pid"])
        ):
            time.sleep(0.05)
        assert windows_backend.pid_active(payload["pid"]) is False
        assert windows_backend.pid_active(payload["descendant_pid"]) is False
    finally:
        if windows_backend.pid_active(payload["pid"]):
            _kill(payload["pid"])
        if windows_backend.pid_active(payload["descendant_pid"]):
            _kill(payload["descendant_pid"])


def test_legacy_gap_before_assignment_leaves_a_suspended_process(tmp_path: Path) -> None:
    import windows_backend

    result = tmp_path / "owner.json"
    folder = tmp_path / "work"
    completed = _owner("win-legacy-gap", folder, result)
    payload = json.loads(result.read_text(encoding="utf-8"))
    survived = False
    try:
        assert completed.returncode == 9
        assert payload["actual_containment"] == "OWNERSHIP_UNCERTAIN"
        time.sleep(0.3)
        survived = windows_backend.pid_active(payload["pid"])
        assert survived is True
        assert not (folder / "side.txt").exists()
    finally:
        if windows_backend.pid_active(payload["pid"]):
            _kill(payload["pid"])

"""Linux policy experiments. Forking cases run in a fresh interpreter."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="Linux park and cgroup probe")
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
    import os
    import signal

    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


def _active(pid: int) -> bool:
    import linux_backend

    return linux_backend.pid_active(pid)


def test_cgroup_is_unavailable_and_default_policy_does_not_exec(tmp_path: Path) -> None:
    import linux_backend
    from lifecycle_contract import CONTAINMENT_UNAVAILABLE, ProcessLifecycleManager

    available, detail = linux_backend._cgroup_status()
    assert available is False
    assert detail.startswith("CONTAINMENT_UNAVAILABLE")
    report = ProcessLifecycleManager().probe_capabilities()
    assert report["descendant_available"] is False
    assert report["actual_if_requested"] == CONTAINMENT_UNAVAILABLE
    session = ProcessLifecycleManager().run("side", time.monotonic() + 5, tmp_path)
    assert session.pid == 0
    assert session.worker_executed is False
    assert not (tmp_path / "side.txt").exists()


def test_explicit_direct_child_is_labeled_and_exit_is_verified_by_wait(tmp_path: Path) -> None:
    result = tmp_path / "result.json"
    completed = _owner("linux-direct-ready", tmp_path / "work", result)
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")[-800:]
    payload = json.loads(result.read_text(encoding="utf-8"))
    assert payload["requested_policy"] == "DIRECT_CHILD_ONLY_EXPLICIT"
    assert payload["actual_containment"] == "DIRECT_CHILD_ONLY"
    assert payload["descendant_containment"] == "DIRECT_CHILD_ONLY"
    assert payload["direct_child_ownership"] == "pidfd"
    assert payload["ready"] is True
    assert payload["verified_before_wait"] is False
    assert payload["exit_verified"] is True
    assert payload["exit_verification"] == "EXIT_VERIFIED"


def test_deadline_before_exec_does_not_run_worker_code(tmp_path: Path) -> None:
    result = tmp_path / "result.json"
    folder = tmp_path / "work"
    completed = _owner("linux-deadline", folder, result)
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")[-800:]
    payload = json.loads(result.read_text(encoding="utf-8"))
    assert payload["error"] == "DEADLINE_BEFORE_RELEASE"
    assert payload["exit_verified"] is True
    assert payload["worker_executed"] is False
    assert payload["actual_containment"] == "DIRECT_CHILD_ONLY"
    assert not (folder / "side.txt").exists()


def test_owner_death_before_release_does_not_exec(tmp_path: Path) -> None:
    result = tmp_path / "result.json"
    folder = tmp_path / "work"
    completed = _owner("linux-park-exit", folder, result)
    payload = json.loads(result.read_text(encoding="utf-8"))
    try:
        assert completed.returncode == 9
        assert payload["state"] == "WORKER_CONTAINED"
        assert payload["actual_containment"] == "DIRECT_CHILD_ONLY"
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and _active(payload["pid"]):
            time.sleep(0.05)
        assert _active(payload["pid"]) is False
        assert not (folder / "side.txt").exists()
    finally:
        if _active(payload["pid"]):
            _kill(payload["pid"])


def test_grandchild_survives_explicit_direct_child_owner_exit(tmp_path: Path) -> None:
    result = tmp_path / "result.json"
    folder = tmp_path / "work"
    completed = _owner("linux-direct-exit", folder, result)
    payload = json.loads(result.read_text(encoding="utf-8"))
    try:
        assert completed.returncode == 9, completed.stderr.decode("utf-8", errors="replace")[-800:]
        assert payload["actual_containment"] == "DIRECT_CHILD_ONLY"
        assert payload["ready"] is True
        assert payload["descendant_pid"] > 0
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and _active(payload["pid"]):
            time.sleep(0.05)
        assert _active(payload["pid"]) is False
        assert _active(payload["descendant_pid"]) is True
    finally:
        if _active(payload["pid"]):
            _kill(payload["pid"])
        if _active(payload["descendant_pid"]):
            _kill(payload["descendant_pid"])

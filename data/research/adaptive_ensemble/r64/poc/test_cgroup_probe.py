"""Real cgroup probe. A delegation failure is the result on this host."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from cgroup_lifecycle import kill_is_refused, strict_open  # noqa: E402
from cgroup_probe import CGROUP_DELEGATION_UNAVAILABLE, probe_host  # noqa: E402


def test_probe_does_not_report_kernel_containment() -> None:
    report = probe_host()
    assert report["evidence"] == "REAL"
    assert report["kernel_containment"] is False
    assert report["delegated"] is False
    assert report["status"] == CGROUP_DELEGATION_UNAVAILABLE


def test_strict_policy_does_not_execute_a_worker(tmp_path: Path) -> None:
    session = strict_open(tmp_path, time.monotonic() + 5)
    assert session["evidence"] == "REAL"
    assert session["forked"] is False
    assert session["worker_executed"] is False
    assert session["pid"] == 0
    assert session["error"] == CGROUP_DELEGATION_UNAVAILABLE
    assert session["equivalent_to_descendant_containment"] is False
    assert not (tmp_path / "side.txt").exists()
    assert not (tmp_path / "ready.txt").exists()


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux cgroup mount")
def test_this_host_denies_a_private_child_cgroup() -> None:
    report = probe_host()
    assert report["reason"] == "MKDIR_ERRNO_13"
    assert report["base_writable"] is False
    assert report["procs_present"] is True
    assert report["kill_present"] is True
    assert report["self_cgroup"] == "/init.scope"
    assert report["cap_eff"] == "0000000000000000"
    base = Path(str(report["base"]))
    leftovers = [path.name for path in base.iterdir() if path.name.startswith("r64-probe-")]
    assert leftovers == []


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux cgroup mount")
def test_repeated_probes_leave_no_child_cgroup() -> None:
    base = Path(str(probe_host()["base"]))
    for _ in range(3):
        report = probe_host()
        assert report["delegated"] is False
    leftovers = [path.name for path in base.iterdir() if path.name.startswith("r64-")]
    assert leftovers == []


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux cgroup mount")
def test_kill_of_the_current_cgroup_is_refused() -> None:
    current = Path(str(probe_host()["base"]))
    assert kill_is_refused(current, owned=True) == "CGROUP_KILL_REFUSED"
    assert kill_is_refused(current, owned=False) == "CGROUP_KILL_REFUSED"
    missing = current / "r64-not-created"
    assert kill_is_refused(missing, owned=True) == "CGROUP_KILL_UNAVAILABLE"
    assert current.joinpath("cgroup.kill").is_file()


@pytest.mark.skipif(sys.platform.startswith("linux"), reason="non-Linux probe")
def test_non_linux_probe_is_an_unsupported_platform() -> None:
    report = probe_host()
    assert report["reason"] == "UNSUPPORTED_PLATFORM"

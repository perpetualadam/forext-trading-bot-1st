"""Platform-independent process lifecycle contract.

The caller sees one set of operations. The status record names the mechanism
that was actually armed. Creation success is not containment. A kill call's
return is not exit verification.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

DIRECT_CHILD_ONLY = "DIRECT_CHILD_ONLY"
DESCENDANT_CONTAINMENT_AVAILABLE = "DESCENDANT_CONTAINMENT_AVAILABLE"
DESCENDANT_CONTAINMENT_ACTIVE = "DESCENDANT_CONTAINMENT_ACTIVE"
CONTAINMENT_UNAVAILABLE = "CONTAINMENT_UNAVAILABLE"
OWNERSHIP_UNCERTAIN = "OWNERSHIP_UNCERTAIN"
CLEANUP_INCOMPLETE = "CLEANUP_INCOMPLETE"

REQUIRE_DESCENDANT_CONTAINMENT = "REQUIRE_DESCENDANT_CONTAINMENT"
DIRECT_CHILD_ONLY_EXPLICIT = "DIRECT_CHILD_ONLY_EXPLICIT"


class Session:
    def __init__(self) -> None:
        self.operating_system = sys.platform
        self.mechanisms: tuple[str, ...] = ()
        self.requested_policy = REQUIRE_DESCENDANT_CONTAINMENT
        self.actual_containment = CONTAINMENT_UNAVAILABLE
        self.direct_child_ownership = "none"
        self.descendant_containment = CONTAINMENT_UNAVAILABLE
        self.startup_deadline = "NOT_REACHED"
        self.exit_verification = "NOT_CHECKED"
        self.cleanup = "NOT_STARTED"
        self.unsupported: tuple[str, ...] = ()
        self.state = "NOT_STARTED"
        self.error = "NONE"
        self.pid = 0
        self.ready = False
        self.exit_verified = False
        self.descendant_pid = 0
        self.descendant_alive = False
        self.side_effect_written = False
        self.harness_intervened = False
        self.worker_executed = False
        self.cgroup_path = ""
        self._side: Path | None = None
        self._grand: Path | None = None
        self._ready: Path | None = None
        self._native: dict[str, int] = {}

    def status(self) -> dict[str, object]:
        return {
            "operating_system": self.operating_system,
            "mechanisms": self.mechanisms,
            "requested_policy": self.requested_policy,
            "actual_containment": self.actual_containment,
            "direct_child_ownership": self.direct_child_ownership,
            "descendant_containment": self.descendant_containment,
            "startup_deadline": self.startup_deadline,
            "exit_verification": self.exit_verification,
            "cleanup": self.cleanup,
            "unsupported": self.unsupported,
            "state": self.state,
            "error": self.error,
            "pid": self.pid,
            "ready": self.ready,
            "exit_verified": self.exit_verified,
            "descendant_pid": self.descendant_pid,
            "descendant_alive": self.descendant_alive,
            "side_effect_written": self.side_effect_written,
            "harness_intervened": self.harness_intervened,
            "worker_executed": self.worker_executed,
        }


class ProcessLifecycleManager:
    def __init__(self, *, require_descendant_containment: bool = True) -> None:
        self.require_descendant_containment = require_descendant_containment
        self.requested_policy = (
            REQUIRE_DESCENDANT_CONTAINMENT
            if require_descendant_containment
            else DIRECT_CHILD_ONLY_EXPLICIT
        )

    def probe_capabilities(self) -> dict[str, object]:
        from capability_probe import probe_capabilities

        return probe_capabilities(self.requested_policy)

    def create_suspended_or_parked(
        self,
        mode: str,
        deadline_at: float,
        directory: Path,
        *,
        before_create=None,
    ) -> Session:
        return _backend().create(self, mode, deadline_at, directory, before_create=before_create)

    def establish_containment(self, session: Session) -> Session:
        return _backend().establish(session)

    def start_worker(self, session: Session, deadline_at: float, *, before_release=None) -> Session:
        return _backend().start(session, deadline_at, before_release=before_release)

    def wait_ready(self, session: Session, deadline_at: float) -> Session:
        return _backend().wait_ready(session, deadline_at)

    def terminate(self, session: Session, reason: str) -> Session:
        session.error = reason or session.error
        return _backend().terminate(session)

    def verify_exit(self, session: Session, deadline_s: float = 5.0) -> Session:
        return _backend().verify_exit(session, deadline_s)

    def cleanup(self, session: Session) -> Session:
        return _backend().cleanup(session)

    def get_process_status(self, session: Session) -> dict[str, object]:
        _backend().refresh(session)
        return session.status()

    def run(
        self,
        mode: str,
        deadline_at: float,
        directory: Path,
        *,
        before_release=None,
    ) -> Session:
        session = self.create_suspended_or_parked(mode, deadline_at, directory)
        if session.state == "NOT_STARTED":
            return session
        self.establish_containment(session)
        if session.actual_containment not in {DESCENDANT_CONTAINMENT_ACTIVE, DIRECT_CHILD_ONLY}:
            if session.pid:
                self.terminate(session, session.error or "CONTAINMENT_FAILED")
                self.verify_exit(session)
            return session
        if time.monotonic() >= deadline_at:
            session.startup_deadline = "EXPIRED_BEFORE_RELEASE"
            session.error = "DEADLINE_BEFORE_RELEASE"
            self.terminate(session, "DEADLINE_BEFORE_RELEASE")
            self.verify_exit(session)
            return session
        self.start_worker(session, deadline_at, before_release=before_release)
        if session.state in {"TERMINATION_ATTEMPTED", "EXIT_VERIFIED", "CLEANUP_INCOMPLETE"}:
            return session
        if session.error == "DEADLINE_BEFORE_RELEASE":
            self.terminate(session, "DEADLINE_BEFORE_RELEASE")
            self.verify_exit(session)
            return session
        self.wait_ready(session, deadline_at)
        return session


def _backend():
    if sys.platform == "win32":
        import windows_backend

        return windows_backend
    if sys.platform.startswith("linux"):
        import linux_backend

        return linux_backend
    raise OSError(0, f"UNSUPPORTED_PLATFORM:{sys.platform}")

"""Short-lived owner for crash observation. Synthetic processes only."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def main(argv: list[str]) -> int:
    kind = argv[0]
    result = Path(argv[1])
    directory = Path(argv[2])
    directory.mkdir(parents=True, exist_ok=True)
    if kind == "win-created-exit":
        from lifecycle_contract import ProcessLifecycleManager

        manager = ProcessLifecycleManager()
        session = manager.create_suspended_or_parked("side", time.monotonic() + 5, directory)
        manager.establish_containment(session)
        _write(result, session)
        os._exit(9)
    if kind == "win-running-exit":
        from lifecycle_contract import ProcessLifecycleManager

        manager = ProcessLifecycleManager()
        session = manager.run("grand", time.monotonic() + 5, directory)
        _write(result, session)
        os._exit(9)
    if kind == "win-legacy-gap":
        import windows_backend

        pid, _process = windows_backend.legacy_suspended_without_job(directory)
        result.write_text(json.dumps({"pid": pid, "state": "WORKER_CREATED", "actual_containment": "OWNERSHIP_UNCERTAIN"}), encoding="utf-8")
        os._exit(9)
    if kind == "linux-direct-exit":
        from lifecycle_contract import ProcessLifecycleManager

        manager = ProcessLifecycleManager(require_descendant_containment=False)
        session = manager.run("grand", time.monotonic() + 5, directory)
        _write(result, session)
        os._exit(9)
    if kind == "linux-direct-ready":
        from lifecycle_contract import ProcessLifecycleManager

        manager = ProcessLifecycleManager(require_descendant_containment=False)
        session = manager.run("ready", time.monotonic() + 5, directory)
        manager.terminate(session, "STOP")
        before = session.exit_verified
        manager.verify_exit(session)
        payload = session.status()
        payload["verified_before_wait"] = before
        result.write_text(json.dumps(payload), encoding="utf-8")
        manager.cleanup(session)
        return 0 if not session.harness_intervened else 3
    if kind == "linux-deadline":
        from lifecycle_contract import ProcessLifecycleManager

        def _late(_pid: int) -> None:
            time.sleep(0.45)

        manager = ProcessLifecycleManager(require_descendant_containment=False)
        session = manager.run("side", time.monotonic() + 0.2, directory, before_release=_late)
        result.write_text(json.dumps(session.status()), encoding="utf-8")
        manager.cleanup(session)
        return 0 if not session.harness_intervened else 3
    if kind == "linux-park-exit":
        from lifecycle_contract import ProcessLifecycleManager

        manager = ProcessLifecycleManager(require_descendant_containment=False)
        session = manager.create_suspended_or_parked("side", time.monotonic() + 5, directory)
        manager.establish_containment(session)
        _write(result, session)
        os._exit(9)
    return 2


def _write(result: Path, session) -> None:
    result.write_text(json.dumps(session.status()), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

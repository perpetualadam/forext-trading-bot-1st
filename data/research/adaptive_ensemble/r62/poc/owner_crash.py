"""One-shot owner used to observe handle close on process exit. Synthetic only."""

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
    if kind == "windows-contained":
        from win_containment import launch

        session = launch("grand", time.monotonic() + 5, directory)
        result.write_text(
            json.dumps({"pid": session.pid, "state": session.state, "contained": session.contained, "ready": session.ready}),
            encoding="utf-8",
        )
        os._exit(9)
    if kind == "linux-contained":
        from linux_containment import launch

        session = launch("grand", time.monotonic() + 5, directory)
        result.write_text(
            json.dumps(
                {
                    "pid": session.pid,
                    "state": session.state,
                    "contained": session.contained,
                    "cgroup": session.cgroup,
                    "ready": session.ready,
                }
            ),
            encoding="utf-8",
        )
        os._exit(9)
    if kind == "linux-parked":
        from linux_containment import launch

        def _stall(pid: int) -> None:
            result.write_text(json.dumps({"pid": pid, "state": "WORKER_CREATED"}), encoding="utf-8")
            os._exit(9)

        launch("side", time.monotonic() + 5, directory, after_create=_stall)
        return 0
    if kind == "linux-before-resume":
        from linux_containment import launch

        def _after(_pid: int) -> None:
            time.sleep(0.5)

        session = launch("side", time.monotonic() + 0.2, directory, after_create=_after)
        result.write_text(
            json.dumps(
                {
                    "pid": session.pid,
                    "state": session.state,
                    "error": session.error,
                    "exit_verified": session.exit_verified,
                    "side": session.side_effect_written,
                    "cgroup": session.cgroup,
                }
            ),
            encoding="utf-8",
        )
        session.close()
        return 0
    if kind == "linux-cgroup":
        from linux_containment import cgroup_probe

        result.write_text(json.dumps({"cgroup": cgroup_probe()}), encoding="utf-8")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

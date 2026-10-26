"""Subprocess helper for R.78 lock and recovery tests. No broker calls."""

from __future__ import annotations

import os
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
R69 = ROOT / "data" / "research" / "adaptive_ensemble" / "r69" / "poc"
sys.path.insert(0, str(R69))
sys.path.insert(0, str(ROOT))

import isolation  # noqa: E402

from forex_bot.recovery_owner_lock import RecoveryOwnerLock, current_process_start, host_boot_id, lock_identity  # noqa: E402


def main() -> int:
    mode = sys.argv[1]
    journal = os.environ["R78_JOURNAL"]
    os.environ["CLOSE_JOURNAL_PATH"] = journal
    entered = Path(os.environ["R78_ENTERED"])
    release = Path(os.environ["R78_RELEASE"])
    if mode == "hold":
        lock = RecoveryOwnerLock(journal)
        if not lock.try_acquire():
            print("lock_failed")
            return 1
        entered.write_text("held", encoding="utf-8")
        deadline = time.time() + 20
        while release.read_text(encoding="utf-8") != "go":
            if time.time() > deadline:
                lock.release()
                print("timeout")
                return 1
            time.sleep(0.02)
        lock.release()
        print("released")
        return 0
    if mode == "crash-owner":
        lock = RecoveryOwnerLock(journal)
        if not lock.try_acquire():
            print("lock_failed")
            return 1
        connection = sqlite3.connect(journal, isolation_level=None)
        connection.execute(
            """
            INSERT INTO recovery_runs (
                run_id, state, owner_token, created_at, updated_at, fencing_epoch,
                owner_pid, process_start, boot_id, lock_identity
            ) VALUES ('RUN-CRASH', 'RECOVERY_IN_PROGRESS', 'TOKEN-CRASH', 't', 't', 1, ?, ?, ?, ?)
            """,
            (os.getpid(), current_process_start(), host_boot_id(), lock_identity(journal)),
        )
        connection.close()
        entered.write_text("held", encoding="utf-8")
        os._exit(0)
    print("unknown_mode")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"worker_error {type(exc).__name__} {exc}")
        raise SystemExit(1)

"""Subprocess journal worker. It does not import a broker client."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))

from forex_bot.close_journal import JournalUnavailable, open_journal  # noqa: E402


def main() -> None:
    cmd, path, binding, instrument, trade_id, instance_id, direction, units = sys.argv[1:9]
    journal = open_journal(path)
    try:
        row = journal.reserve(
            account_binding_value=binding,
            position_instance_id=instance_id,
            position_generation=1,
            instrument=instrument,
            trade_id=trade_id,
            direction=direction,
            original_units=units,
            requested_units=units,
        )
        if cmd == "intent":
            token = journal.commit_submission_intent(row["operation_id"])
            print(json.dumps({"ok": True, "operation_id": row["operation_id"], "token": token}))
        else:
            print(json.dumps({"ok": True, "operation_id": row["operation_id"]}))
    except JournalUnavailable as exc:
        print(json.dumps({"ok": False, "reason": exc.reason}))
    finally:
        journal.close()


if __name__ == "__main__":
    main()

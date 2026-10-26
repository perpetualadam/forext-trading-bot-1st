"""Import the operational modules on Linux after isolation is installed."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
R69 = ROOT / "data" / "research" / "adaptive_ensemble" / "r69" / "poc"
sys.path.insert(0, str(R69))
sys.path.insert(0, str(ROOT))

import isolation  # noqa: E402

MODULES = [
    "forex_bot.oanda_client",
    "forex_bot.oanda_exec",
    "forex_bot.bot_loop",
    "forex_bot.startup_recovery",
    "forex_bot.entry_journal",
    "forex_bot.entry_capture",
    "forex_bot.position_recovery",
    "forex_bot.recovery_repair",
    "forex_bot.recovery_owner_lock",
    "forex_bot.broker_entry_evidence",
    "forex_bot.broker_close_evidence",
    "forex_bot.entry_investigation",
    "forex_bot.reconciliation",
    "forex_bot.live_manage",
    "forex_bot.profit_protection",
    "forex_bot.execution",
    "forex_bot.trading",
    "forex_bot.positions",
]


def main() -> int:
    failed = 0
    for name in MODULES:
        try:
            __import__(name)
        except ModuleNotFoundError as exc:
            print(f"IMPORT_BLOCKED_DEPENDENCY {name} {exc.name}")
            failed += 1
        except Exception as exc:
            print(f"IMPORT_FAILED_PLATFORM {name} {type(exc).__name__} {exc}")
            traceback.print_exc()
            failed += 1
        else:
            print(f"IMPORT_PASSED {name}")
    print(f"ISOLATION_READY {isolation.ISOLATION_READY}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

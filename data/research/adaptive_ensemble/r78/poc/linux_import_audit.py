"""Import operational modules under the R.69 isolation harness. No package installation."""

from __future__ import annotations

import sys
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
    "forex_bot.reconciliation",
    "forex_bot.live_manage",
    "forex_bot.profit_protection",
    "forex_bot.entry_investigation",
]


def main() -> int:
    print("ISOLATION_READY", isolation.ISOLATION_READY)
    for name in MODULES:
        try:
            __import__(name)
        except ModuleNotFoundError as exc:
            print(f"IMPORT_BLOCKED_DEPENDENCY {name} {exc}")
        except Exception as exc:
            print(f"IMPORT_FAILED_PLATFORM {name} {type(exc).__name__}: {exc}")
        else:
            print(f"IMPORT_PASSED {name}")
    network = [item for item in isolation.ATTEMPTS if item[0] in {"socket.connect", "socket.create_connection", "psycopg2.connect"}]
    print("NETWORK_ATTEMPTS", len(network))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

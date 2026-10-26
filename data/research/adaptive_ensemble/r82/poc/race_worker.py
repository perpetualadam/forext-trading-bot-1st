"""R.82 restart and final-check workers. Isolation is imported first."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
R69 = ROOT / "data" / "research" / "adaptive_ensemble" / "r69" / "poc"
sys.path.insert(0, str(R69))
sys.path.insert(0, str(ROOT))

import isolation  # noqa: E402

from forex_bot import oanda_client  # noqa: E402
from forex_bot.position_recovery import durable_positions  # noqa: E402
from forex_bot.positions import position_management_permitted, positions  # noqa: E402
from forex_bot.startup_recovery import execute_startup_sequence, live_management_permitted  # noqa: E402
import forex_bot.config as config_mod  # noqa: E402

ACCOUNT = "001-002-0000001-003"
WRITES = {"OrderCreate", "PositionClose"}


class RecordingAPI:
    def __init__(self) -> None:
        self._request_params: dict = {}

    def request(self, request_obj):
        name = type(request_obj).__name__
        if name in WRITES:
            raise isolation.IsolationBreach(name)
        if name == "AccountSummary":
            return {"account": {"NAV": "10000", "balance": "10000", "currency": "GBP"}}
        return {"prices": [], "candles": []}


def _view(mode: str) -> dict:
    rows = durable_positions()
    row = rows[0] if rows else None
    if mode == "incomplete":
        return {"snapshot": "INCOMPLETE", "trades": []}
    if mode == "empty" or row is None:
        return {"snapshot": "COMPLETE_EMPTY", "trades": []}
    trade = {
        "trade_id": row["trade_id"],
        "instrument": row["instrument"],
        "direction": row["direction"],
        "units": str(row["units"]),
        "account_binding": row["account_binding"],
        "provenance": "bot_managed",
    }
    if mode == "remaining":
        trade["units"] = "600"
    elif mode == "wrong-trade":
        trade["trade_id"] = "T-OTHER"
    elif mode == "wrong-account":
        trade["account_binding"] = "0" * 64
    elif mode == "missing":
        return {"snapshot": "COMPLETE", "trades": []}
    return {"snapshot": "COMPLETE", "trades": [trade]}


def _wait() -> None:
    entered = os.environ.get("R82_ENTERED", "")
    release = os.environ.get("R82_RELEASE", "")
    if not entered:
        return
    Path(entered).write_text("entered", encoding="utf-8")
    if not release:
        return
    deadline = time.time() + 15
    while Path(release).read_text(encoding="utf-8") != "go":
        if time.time() > deadline:
            raise TimeoutError("release barrier")
        time.sleep(0.01)


def main() -> int:
    mode = sys.argv[1]
    os.environ["CLOSE_JOURNAL_PATH"] = os.environ["R82_JOURNAL"]
    os.environ["CLOSE_JOURNAL_BUSY_MS"] = "300"
    os.environ["EXECUTION_MODE"] = "paper_broker"
    os.environ["OANDA_MAX_RETRIES"] = "1"
    config_mod.Config.OANDA_ACCOUNT_ID = ACCOUNT
    oanda_client._api = RecordingAPI()
    if mode == "successor-startup":
        _wait()
        report = execute_startup_sequence(_view(os.environ.get("R82_VIEW", "empty")))
        print(f"state={report.get('state')}")
        print(f"management={int(live_management_permitted())}")
        return 0
    report = execute_startup_sequence(_view(os.environ.get("R82_VIEW", "remaining")))
    print(f"state={report.get('state')}")
    print(f"management={int(live_management_permitted())}")
    resident = positions.get("EUR_USD")
    print(f"in_book={int(resident is not None)}")
    print(f"manageable={int(position_management_permitted(resident))}")
    for item in report.get("decisions") or []:
        print(f"decision={item.get('state')}:{item.get('reason')}")
    if mode == "restart-cycle":
        import asyncio

        from forex_bot import bot_loop

        asyncio.run(bot_loop._execute_bot_cycle(["EUR_USD"]))
        print("cycle=1")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"worker_error={type(exc).__name__}:{exc}")
        raise SystemExit(1)

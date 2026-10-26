"""Subprocess worker for the R.75 guarded close. Synthetic recorder only."""

from __future__ import annotations

import asyncio
import json
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

from forex_bot import oanda_client  # noqa: E402
from forex_bot.oanda_rate_limit import reset_oanda_rate_limiter_for_tests  # noqa: E402
from forex_bot.broker_close_evidence import run_guarded_live_close  # noqa: E402
from forex_bot.oanda_exec import (  # noqa: E402
    CloseGuardRefusal,
    _place_market_order_sync,
    _submit_position_close_body,
    execute_oanda_market_close,
)
from forex_bot.positions import Position, positions  # noqa: E402
from forex_bot.trading import execute_trade  # noqa: E402
import forex_bot.config as config_mod  # noqa: E402

ACCOUNT = "001-002-0000001-003"


class RecordingAPI:
    def request(self, request_obj):
        name = type(request_obj).__name__
        if name == "TransactionDetails":
            return {
                "transaction": {
                    "id": "TX1",
                    "type": "ORDER_FILL",
                    "accountID": ACCOUNT,
                    "instrument": "EUR_USD",
                    "units": "-1000",
                    "tradesClosed": [{"tradeID": "T1", "units": "1000"}],
                }
            }
        if name != "PositionClose":
            raise isolation.IsolationBreach(name)
        entered = os.environ.get("R75_ENTERED", "")
        release = os.environ.get("R75_RELEASE", "")
        if entered:
            Path(entered).write_text("entered", encoding="utf-8")
            deadline = time.time() + 5
            while Path(release).read_text(encoding="utf-8") != "go":
                if time.time() > deadline:
                    raise TimeoutError("release barrier")
                time.sleep(0.01)
        connection = sqlite3.connect(os.environ["R75_RECORDER"], timeout=5, isolation_level=None)
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT INTO submissions (instrument, units) VALUES (?, ?)",
            ("EUR_USD", "1000"),
        )
        connection.execute("COMMIT")
        connection.close()
        return {
            "longOrderFillTransaction": {
                "id": "TX1",
                "type": "ORDER_FILL",
                "instrument": "EUR_USD",
                "units": "-1000",
            }
        }


def _position() -> Position:
    return Position(
        symbol="EUR_USD",
        direction="BUY",
        units=1000.0,
        entry_price=1.1,
        stop_loss=1.05,
        take_profit=1.2,
        open_time=1.0,
        strategy_name="existing_strategy",
        rl_state="held",
        execution_kind="live",
        broker_trade_ids="T1",
        broker_order=True,
        position_instance_id=os.environ.get("R75_INSTANCE", "instance-a"),
        position_generation=1,
    )


def main() -> None:
    os.environ["OANDA_MAX_RETRIES"] = "1"
    os.environ["OANDA_MAX_REQUESTS_PER_SEC"] = "120"
    os.environ["EXECUTION_MODE"] = "paper_broker"
    config_mod.Config.OANDA_ACCOUNT_ID = ACCOUNT
    reset_oanda_rate_limiter_for_tests()
    oanda_client._api = RecordingAPI()
    command = sys.argv[1]
    if command == "close":
        positions["EUR_USD"] = _position()
        operation = asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r75"))
        print(json.dumps({"ok": True, "state": operation.confirmation_state, "error": operation.error_classification}))
        return
    try:
        if command == "execute_trade":
            asyncio.run(
                execute_trade("EUR_USD", "existing_strategy", "BUY", 1000, 1.1, 1.0, 1.2, execution_kind="live")
            )
        elif command == "market_close":
            asyncio.run(execute_oanda_market_close("EUR_USD", 1000, "BUY", 1.1, execution_kind="live"))
        elif command == "place":
            _place_market_order_sync("EUR_USD", 1000, "BUY")
        elif command == "submit":
            _submit_position_close_body("EUR_USD", 1000, "BUY")
        else:
            print(json.dumps({"ok": False, "error": "unknown_command"}))
            return
        print(json.dumps({"ok": True, "error": ""}))
    except (CloseGuardRefusal, RuntimeError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__}))


if __name__ == "__main__":
    main()

"""R.84 close-restart workers. Isolation is imported before operational modules."""

from __future__ import annotations

import asyncio
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
from forex_bot.broker_close_evidence import run_guarded_live_close  # noqa: E402
from forex_bot.close_journal import account_binding, active_journal  # noqa: E402
from forex_bot.position_recovery import durable_positions, persist_bot_position  # noqa: E402
from forex_bot.positions import Position, position_management_permitted, positions  # noqa: E402
from forex_bot.startup_recovery import execute_startup_sequence, live_management_permitted  # noqa: E402
import forex_bot.config as config_mod  # noqa: E402
import forex_bot.live_safety as live_safety  # noqa: E402

ACCOUNT = "001-002-0000001-003"
WRITES = {"OrderCreate", "PositionClose"}


class RecordingAPI:
    def __init__(self, recorder: str, shape: str) -> None:
        self.recorder = recorder
        self.shape = shape
        self._request_params: dict = {}

    def request(self, request_obj):
        name = type(request_obj).__name__
        if name in WRITES:
            connection = sqlite3.connect(self.recorder)
            connection.execute("INSERT INTO submissions (kind) VALUES (?)", (name,))
            connection.commit()
            connection.close()
        elif name not in {"TransactionDetails", "AccountSummary", "InstrumentCandles"}:
            raise isolation.IsolationBreach(name)
        if name == "PositionClose":
            return {
                "orderFillTransaction": {
                    "id": "TX-R84",
                    "type": "ORDER_FILL",
                    "instrument": "EUR_USD",
                    "units": "-1000" if self.shape == "full" else "-400",
                }
            }
        if name == "TransactionDetails":
            if self.shape == "ambiguous":
                return {
                    "transaction": {
                        "id": "TX-R84",
                        "type": "ORDER_FILL",
                        "accountID": ACCOUNT,
                        "instrument": "EUR_USD",
                        "units": "-1000",
                    }
                }
            if self.shape == "partial":
                return {
                    "transaction": {
                        "id": "TX-R84",
                        "type": "ORDER_FILL",
                        "accountID": ACCOUNT,
                        "instrument": "EUR_USD",
                        "orderID": "ORD-R84",
                        "units": "-400",
                        "tradeReduced": {"tradeID": "T1", "units": "-400"},
                    }
                }
            return {
                "transaction": {
                    "id": "TX-R84",
                    "type": "ORDER_FILL",
                    "accountID": ACCOUNT,
                    "instrument": "EUR_USD",
                    "orderID": "ORD-R84",
                    "units": "-1000",
                    "tradesClosed": [{"tradeID": "T1", "units": "-1000"}],
                }
            }
        return {"account": {"NAV": "10000"}, "candles": []}


def _wait(entered: str, release: str) -> None:
    Path(entered).write_text("entered", encoding="utf-8")
    deadline = time.time() + 15
    while True:
        try:
            if Path(release).read_text(encoding="utf-8") == "go":
                return
        except OSError:
            pass
        if time.time() > deadline:
            raise TimeoutError("release barrier")
        time.sleep(0.01)


def _view(mode: str) -> dict:
    rows = durable_positions()
    row = rows[0] if rows else None
    if mode == "empty" or row is None:
        return {"snapshot": "COMPLETE_EMPTY", "trades": []}
    trade = {
        "trade_id": row["trade_id"],
        "instrument": row["instrument"],
        "direction": row["direction"],
        "units": "1000" if mode == "conflict-open" else str(row["units"]),
        "account_binding": row["account_binding"],
        "provenance": "bot_managed",
    }
    return {"snapshot": "COMPLETE", "trades": [trade]}


def _print_recovery(report: dict) -> None:
    resident = positions.get("EUR_USD")
    print(f"state={report.get('state')}")
    print(f"management={int(live_management_permitted())}")
    print(f"manageable={int(position_management_permitted(resident))}")
    journal = active_journal()
    close = journal._conn.execute(
        "SELECT confirmation_state, network_permit, confirmed_units, remaining_units FROM close_operations ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    if close is not None:
        print(f"close_state={close['confirmation_state']}")
        print(f"close_permit={int(close['network_permit'])}")
        print(f"confirmed={close['confirmed_units']}")
        print(f"remaining={close['remaining_units']}")
    row = journal._conn.execute(
        "SELECT units, trade_id, profit_protection_exit_pips FROM managed_positions ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    if row is not None:
        print(f"durable_units={row['units']}")
        print(f"durable_trade={row['trade_id']}")
        print(f"ratchet={row['profit_protection_exit_pips']}")


def main() -> int:
    mode = sys.argv[1]
    os.environ["CLOSE_JOURNAL_PATH"] = os.environ["R84_JOURNAL"]
    os.environ["CLOSE_JOURNAL_BUSY_MS"] = "300"
    os.environ["EXECUTION_MODE"] = "paper_broker"
    os.environ["OANDA_MAX_RETRIES"] = "1"
    os.environ["OANDA_MAX_REQUESTS_PER_SEC"] = "120"
    config_mod.Config.OANDA_ACCOUNT_ID = ACCOUNT
    live_safety.assert_new_live_exposure_allowed = lambda **kwargs: None
    shape = os.environ.get("R84_SHAPE", "full")
    oanda_client._api = RecordingAPI(os.environ["R84_RECORDER"], shape)
    if mode == "successor":
        report = execute_startup_sequence(_view(os.environ.get("R84_VIEW", "match")))
        _print_recovery(report)
        if os.environ.get("R84_CYCLE") == "1":
            from forex_bot import bot_loop

            asyncio.run(bot_loop._execute_bot_cycle(["EUR_USD"]))
            print("cycle=1")
        return 0
    report = execute_startup_sequence({"snapshot": "COMPLETE_EMPTY", "trades": []})
    print(f"startup={report.get('state')}")
    binding = account_binding(ACCOUNT)
    pos = Position(
        symbol="EUR_USD",
        direction="BUY",
        units=1000.0,
        entry_price=1.1,
        stop_loss=1.05,
        take_profit=1.2,
        open_time=1.0,
        strategy_name="r84",
        rl_state="held",
        execution_kind="live",
        broker_trade_ids="T1",
        position_instance_id="INST-R84",
        position_generation=1,
        max_profit_pips=0.0,
        profit_protection_active=False,
        min_profit_pips=0.0,
        max_adverse_pips=0.0,
        profit_protection_exit_pips=40.0,
    )
    persist_bot_position(pos, binding)
    positions["EUR_USD"] = pos
    asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r84"))
    _wait(os.environ["R84_ENTERED"], os.environ["R84_RELEASE"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"worker_error={type(exc).__name__}:{exc}")
        raise SystemExit(1)

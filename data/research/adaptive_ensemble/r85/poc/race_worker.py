"""R.85 successor and termination worker. Isolation is imported before operational modules."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
R69 = ROOT / "data" / "research" / "adaptive_ensemble" / "r69" / "poc"
sys.path.insert(0, str(R69))
sys.path.insert(0, str(ROOT))

import isolation  # noqa: E402

from forex_bot import config as config_mod  # noqa: E402
from forex_bot import live_safety, oanda_client  # noqa: E402
from forex_bot.close_journal import account_binding  # noqa: E402
from forex_bot.position_recovery import durable_positions, quarantined_positions  # noqa: E402
from forex_bot.positions import Position, positions  # noqa: E402
from forex_bot.startup_recovery import (  # noqa: E402
    current_fencing_epoch,
    execute_startup_sequence,
    live_management_permitted,
)

ACCOUNT = "001-002-0000001-003"


class Broker:
    def __init__(self, recorder: str, shape: str) -> None:
        self.recorder = recorder
        self.shape = shape
        self._request_params: dict = {}

    def request(self, request_obj):
        import sqlite3

        name = type(request_obj).__name__
        if name in {"OrderCreate", "PositionClose"}:
            connection = sqlite3.connect(self.recorder)
            connection.execute("INSERT INTO submissions (kind) VALUES (?)", (name,))
            connection.commit()
            connection.close()
        elif name not in {
            "TransactionDetails",
            "AccountSummary",
            "InstrumentCandles",
            "InstrumentsCandles",
            "PricingInfo",
        }:
            raise isolation.IsolationBreach(name)
        if name == "PositionClose":
            return {
                "longOrderFillTransaction": {
                    "id": "TX-R85-KILL",
                    "type": "ORDER_FILL",
                    "instrument": "EUR_USD",
                    "units": "-1000",
                }
            }
        if name == "TransactionDetails":
            return {
                "transaction": {
                    "id": "TX-R85-KILL",
                    "type": "ORDER_FILL",
                    "accountID": ACCOUNT,
                    "instrument": "EUR_USD",
                    "units": "-1000",
                    "tradesClosed": [{"tradeID": "T1", "units": "-1000"}],
                }
            }
        return {"account": {"NAV": "10000"}, "candles": []}


def _view(kind: str) -> dict:
    if kind == "blocked":
        return {"snapshot": "REQUEST_FAILED", "trades": []}
    trades = []
    for row in durable_positions():
        units = str(row["units"])
        if kind == "remainder":
            units = "600"
        elif kind == "zero":
            units = "0"
        trades.append(
            {
                "trade_id": row["trade_id"],
                "instrument": row["instrument"],
                "direction": row["direction"],
                "units": units,
                "account_binding": row["account_binding"],
                "provenance": "bot_managed",
            }
        )
    if kind == "empty":
        return {"snapshot": "COMPLETE_EMPTY", "trades": []}
    return {"snapshot": "COMPLETE", "trades": trades}


def _print_recovery(report: dict) -> None:
    print(f"state={report.get('state')}")
    print(f"reason={report.get('reason')}")
    print(f"epoch={current_fencing_epoch()}")
    print(f"management={int(live_management_permitted())}")
    decisions = list(report.get("decisions") or [])
    manageable = any(bool(item.get("manageable")) for item in decisions)
    print(f"manageable={int(manageable)}")
    print(f"quarantine_count={len(quarantined_positions)}")
    print(f"memory_count={len(positions)}")


def main() -> int:
    mode = sys.argv[1]
    os.environ["CLOSE_JOURNAL_PATH"] = os.environ["R85_JOURNAL"]
    os.environ["CLOSE_JOURNAL_BUSY_MS"] = "300"
    os.environ["EXECUTION_MODE"] = "paper_broker"
    os.environ["OANDA_MAX_RETRIES"] = "1"
    os.environ["OANDA_MAX_REQUESTS_PER_SEC"] = "120"
    config_mod.Config.OANDA_ACCOUNT_ID = ACCOUNT
    live_safety.assert_new_live_exposure_allowed = lambda **kwargs: None
    oanda_client._api = Broker(os.environ["R85_RECORDER"], os.environ.get("R85_SHAPE", "full"))
    if mode == "successor":
        report = execute_startup_sequence(_view(os.environ.get("R85_VIEW", "match")))
        _print_recovery(report)
        return 0
    if mode == "pause-after-full":
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
            strategy_name="r85",
            rl_state="held",
            execution_kind="live",
            broker_trade_ids="T1",
            position_instance_id="INST-R85-KILL",
            position_generation=1,
            max_profit_pips=0.0,
            profit_protection_active=False,
            min_profit_pips=0.0,
            max_adverse_pips=0.0,
            profit_protection_exit_pips=40.0,
        )
        positions["EUR_USD"] = pos
        from forex_bot.broker_close_evidence import run_guarded_live_close

        asyncio.run(run_guarded_live_close(pos, reason="r85-kill"))
        entered = Path(os.environ["R85_ENTERED"])
        release = Path(os.environ["R85_RELEASE"])
        entered.write_text("1", encoding="utf-8")
        deadline = __import__("time").time() + 15
        while not release.exists():
            if __import__("time").time() > deadline:
                print("release_timeout")
                return 0
            __import__("time").sleep(0.05)
        return 0
    print(f"unknown_mode={mode}")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"worker_error={type(exc).__name__}:{exc}")
        raise SystemExit(1)

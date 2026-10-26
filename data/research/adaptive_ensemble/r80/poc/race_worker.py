"""Separate-process worker for R.80 entry and close races.

Each process obtains recovery authority only by execute_startup_sequence.
A cold mode does not start recovery and must not submit.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
R69 = ROOT / "data" / "research" / "adaptive_ensemble" / "r69" / "poc"
sys.path.insert(0, str(R69))
sys.path.insert(0, str(ROOT))

import isolation  # noqa: E402

from forex_bot import oanda_client  # noqa: E402
from forex_bot.broker_close_evidence import run_guarded_live_close  # noqa: E402
from forex_bot.close_journal import JournalUnavailable, account_binding  # noqa: E402
from forex_bot.entry_journal import EntryGuardRefusal, begin_entry_submission  # noqa: E402
from forex_bot.market_provenance import mint_live_quote  # noqa: E402
from forex_bot.oanda_exec import CloseGuardRefusal, _place_market_order_open_sync  # noqa: E402
from forex_bot.oanda_rate_limit import reset_oanda_rate_limiter_for_tests  # noqa: E402
from forex_bot.position_recovery import durable_positions  # noqa: E402
from forex_bot.positions import positions  # noqa: E402
from forex_bot.startup_recovery import (  # noqa: E402
    current_fencing_epoch,
    execute_startup_sequence,
    live_management_permitted,
)
import forex_bot.config as config_mod  # noqa: E402
import forex_bot.live_safety as live_safety  # noqa: E402

ACCOUNT = "001-002-0000001-003"


def _wait_barrier() -> None:
    entered = os.environ.get("R80_ENTERED", "")
    release = os.environ.get("R80_RELEASE", "")
    if not entered:
        return
    Path(entered).write_text("entered", encoding="utf-8")
    deadline = time.time() + 15
    while Path(release).read_text(encoding="utf-8") != "go":
        if time.time() > deadline:
            raise TimeoutError("release barrier")
        time.sleep(0.01)


class RecordingAPI:
    def __init__(self) -> None:
        self._request_params: dict = {}

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
        if name not in {"OrderCreate", "PositionClose"}:
            raise isolation.IsolationBreach(name)
        _wait_barrier()
        recorder = os.environ.get("R80_RECORDER", "")
        if recorder:
            connection = sqlite3.connect(recorder, timeout=5, isolation_level=None)
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT INTO submissions (kind) VALUES (?)", (name,))
            connection.execute("COMMIT")
            connection.close()
        if name == "PositionClose":
            return {
                "longOrderFillTransaction": {
                    "id": "TX1",
                    "type": "ORDER_FILL",
                    "instrument": "EUR_USD",
                    "units": "-1000",
                }
            }
        client = os.environ.get("R80_CLIENT", "client-r80")
        return {
            "orderCreateTransaction": {"id": "O-ORDER"},
            "orderFillTransaction": {
                "id": "F-1",
                "type": "ORDER_FILL",
                "accountID": ACCOUNT,
                "instrument": "EUR_USD",
                "units": "1000",
                "price": "1.10000",
                "orderID": "O-ORDER",
                "clientExtensions": {"id": client},
                "tradeOpened": {"tradeID": "T-RACE", "units": "1000", "price": "1.10000"},
            },
        }


def _startup_from_journal() -> str:
    rows = durable_positions()
    trades = [
        {
            "trade_id": row["trade_id"],
            "instrument": row["instrument"],
            "direction": row["direction"],
            "units": str(row["units"]),
            "account_binding": row["account_binding"],
            "provenance": "bot_managed",
        }
        for row in rows
    ]
    view = {"snapshot": "COMPLETE" if trades else "COMPLETE_EMPTY", "trades": trades}
    report = execute_startup_sequence(view)
    print(f"pid={os.getpid()}")
    print(f"epoch={current_fencing_epoch()}")
    print(f"state={report.get('state')}")
    return str(report.get("state") or "")


def _reserve():
    return begin_entry_submission(
        account_binding_value=account_binding(ACCOUNT),
        instrument="EUR_USD",
        direction="BUY",
        requested_units=Decimal("1000"),
        position_instance_id=os.environ.get("R80_INSTANCE", "INST-R80"),
        position_generation=1,
        client_order_id=os.environ.get("R80_CLIENT", "client-r80"),
        strategy_name="r80",
        stop_loss="1.09000",
        take_profit="1.12000",
        entry_reference="decision-r80",
        atr_at_entry_pips="8",
    )


def main() -> int:
    mode = sys.argv[1]
    os.environ["CLOSE_JOURNAL_PATH"] = os.environ["R80_JOURNAL"]
    os.environ["CLOSE_JOURNAL_BUSY_MS"] = "300"
    os.environ["EXECUTION_MODE"] = "paper_broker"
    os.environ["OANDA_MAX_RETRIES"] = "1"
    os.environ["OANDA_MAX_REQUESTS_PER_SEC"] = "120"
    config_mod.Config.OANDA_ACCOUNT_ID = ACCOUNT
    reset_oanda_rate_limiter_for_tests()
    live_safety.assert_new_live_exposure_allowed = lambda **kwargs: None
    oanda_client._api = RecordingAPI()
    try:
        if mode == "reserve":
            _reserve()
            print("reserved")
            return 0
        if mode == "startup-only":
            _startup_from_journal()
            print(f"management={int(live_management_permitted())}")
            return 0
        if mode == "entry-cold":
            try:
                permit = _reserve()
                _place_market_order_open_sync(
                    "EUR_USD", 1000, "BUY", permit.client_order_id, 1.09, 1.12, mint_live_quote("EUR_USD"), entry_permit=permit
                )
            except (JournalUnavailable, EntryGuardRefusal, RuntimeError, TimeoutError) as exc:
                print(f"refused={getattr(exc, 'reason', type(exc).__name__)}")
                return 0
            print("submitted")
            return 0
        if mode == "startup-entry":
            _startup_from_journal()
            if not live_management_permitted():
                print("refused=recovery_authority_absent")
                return 0
            permit = _reserve()
            _place_market_order_open_sync(
                "EUR_USD", 1000, "BUY", permit.client_order_id, 1.09, 1.12, mint_live_quote("EUR_USD"), entry_permit=permit
            )
            print("submitted")
            return 0
        if mode == "close-cold":
            from forex_bot.positions import Position

            pos = Position(
                symbol="EUR_USD",
                direction="BUY",
                units=1000.0,
                entry_price=1.1,
                stop_loss=1.05,
                take_profit=1.2,
                open_time=1.0,
                strategy_name="r80",
                rl_state="held",
                execution_kind="live",
                broker_trade_ids="T1",
                position_instance_id="INST-CLOSE",
                position_generation=1,
            )
            operation = asyncio.run(run_guarded_live_close(pos, reason="r80-cold"))
            print(f"state={operation.confirmation_state}")
            print(f"reason={operation.reason}")
            return 0
        if mode == "startup-close":
            _startup_from_journal()
            if not live_management_permitted():
                print("refused=recovery_authority_absent")
                return 0
            pos = positions.get("EUR_USD")
            if pos is None:
                print("refused=position_absent")
                return 0
            operation = asyncio.run(run_guarded_live_close(pos, reason="r80"))
            print(f"state={operation.confirmation_state}")
            print(f"reason={operation.reason}")
            return 0
    except (JournalUnavailable, EntryGuardRefusal, CloseGuardRefusal, RuntimeError, TimeoutError) as exc:
        print(f"refused={getattr(exc, 'reason', type(exc).__name__)}")
        return 0
    print("unknown_mode")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"worker_error={type(exc).__name__}")
        raise SystemExit(1)

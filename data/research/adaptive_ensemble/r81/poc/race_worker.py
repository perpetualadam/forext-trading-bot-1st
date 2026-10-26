"""Separate-process worker for R.81 rate-limit, crash, repair, and restart tests.

Isolation is imported before any operational module. Recovery authority comes
only from execute_startup_sequence. The rate-limit and request barriers are
instrumentation around the operational sinks. They do not replace those sinks.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
import time
import uuid
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
R69 = ROOT / "data" / "research" / "adaptive_ensemble" / "r69" / "poc"
sys.path.insert(0, str(R69))
sys.path.insert(0, str(ROOT))

import isolation  # noqa: E402

from forex_bot import oanda_client  # noqa: E402
from forex_bot.broker_close_evidence import run_guarded_live_close  # noqa: E402
from forex_bot.close_journal import JournalUnavailable, account_binding, active_journal  # noqa: E402
from forex_bot.entry_journal import EntryGuardRefusal, begin_entry_submission  # noqa: E402
from forex_bot.market_provenance import mint_live_quote  # noqa: E402
from forex_bot.oanda_exec import CloseGuardRefusal, _place_market_order_open_sync  # noqa: E402
from forex_bot.oanda_rate_limit import reset_oanda_rate_limiter_for_tests  # noqa: E402
from forex_bot.position_recovery import durable_positions  # noqa: E402
from forex_bot.positions import positions  # noqa: E402
from forex_bot.recovery_owner_lock import (  # noqa: E402
    RecoveryOwnerLock,
    current_process_start,
    host_boot_id,
    lock_identity,
)
from forex_bot.startup_recovery import (  # noqa: E402
    current_fencing_epoch,
    execute_startup_sequence,
    live_management_permitted,
)
import forex_bot.config as config_mod  # noqa: E402
import forex_bot.live_safety as live_safety  # noqa: E402
import forex_bot.oanda_rate_limit as rate_limit  # noqa: E402

ACCOUNT = "001-002-0000001-003"
WRITES = {"OrderCreate", "PositionClose"}


def _signal_and_wait() -> None:
    entered = os.environ.get("R81_ENTERED", "")
    release = os.environ.get("R81_RELEASE", "")
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


def _install_slot_barrier() -> None:
    if os.environ.get("R81_PAUSE") != "slot":
        return
    original = rate_limit.acquire_oanda_rest_slot

    def wrapped() -> float:
        _signal_and_wait()
        return original()

    rate_limit.acquire_oanda_rest_slot = wrapped


class RecordingAPI:
    def __init__(self) -> None:
        self._request_params: dict = {}

    def request(self, request_obj):
        name = type(request_obj).__name__
        if name == "TransactionDetails":
            units = os.environ.get("R81_TX_UNITS", "-1000")
            closed = os.environ.get("R81_TX_CLOSED", "1000")
            return {
                "transaction": {
                    "id": "TX1",
                    "type": "ORDER_FILL",
                    "accountID": ACCOUNT,
                    "instrument": "EUR_USD",
                    "units": units,
                    "tradesClosed": [{"tradeID": "T1", "units": closed}],
                }
            }
        if name not in WRITES:
            raise isolation.IsolationBreach(name)
        pause = os.environ.get("R81_PAUSE", "")
        if pause == "request-before":
            _signal_and_wait()
        recorder = os.environ.get("R81_RECORDER", "")
        if recorder:
            connection = sqlite3.connect(recorder, timeout=5, isolation_level=None)
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT INTO submissions (kind) VALUES (?)", (name,))
            connection.execute("COMMIT")
            connection.close()
        if pause == "request-after":
            _signal_and_wait()
        if name == "PositionClose":
            body = os.environ.get("R81_CLOSE_BODY", "fill")
            if body == "reject":
                return {"longOrderRejectTransaction": {"id": "RJ", "type": "ORDER_REJECT"}}
            units = os.environ.get("R81_FILL_UNITS", "-1000")
            return {
                "longOrderFillTransaction": {
                    "id": "TX1",
                    "type": "ORDER_FILL",
                    "instrument": "EUR_USD",
                    "units": units,
                }
            }
        if os.environ.get("R81_ENTRY_FAIL") == "timeout":
            raise TimeoutError("synthetic entry timeout")
        client = os.environ.get("R81_CLIENT", "client-r81")
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
                "tradeOpened": {"tradeID": "T-R81", "units": "1000", "price": "1.10000"},
            },
        }


def _view(snapshot: str) -> dict:
    if snapshot == "COMPLETE_EMPTY":
        return {"snapshot": "COMPLETE_EMPTY", "trades": []}
    if snapshot == "INCOMPLETE":
        return {
            "snapshot": "COMPLETE",
            "trades": [
                {
                    "trade_id": "",
                    "instrument": "EUR_USD",
                    "direction": "BUY",
                    "units": "1000",
                    "provenance": "bot_managed",
                }
            ],
        }
    trades = [
        {
            "trade_id": row["trade_id"],
            "instrument": row["instrument"],
            "direction": row["direction"],
            "units": str(row["units"]),
            "account_binding": row["account_binding"],
            "provenance": "bot_managed",
        }
        for row in durable_positions()
    ]
    return {"snapshot": "COMPLETE" if trades else "COMPLETE_EMPTY", "trades": trades}


def _startup(snapshot: str = "durable") -> None:
    report = execute_startup_sequence(_view(snapshot))
    print(f"pid={os.getpid()}")
    print(f"epoch={current_fencing_epoch()}")
    print(f"state={report.get('state')}")
    print(f"management={int(live_management_permitted())}")
    journal = active_journal()
    run = journal._conn.execute(
        "SELECT run_id, owner_token, state FROM recovery_runs ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    if run is not None:
        print(f"run_id={run['run_id']}")
        print(f"owner_token={run['owner_token']}")
        print(f"run_state={run['state']}")


def _reserve():
    return begin_entry_submission(
        account_binding_value=account_binding(ACCOUNT),
        instrument="EUR_USD",
        direction="BUY",
        requested_units=Decimal("1000"),
        position_instance_id=os.environ.get("R81_INSTANCE", "INST-R81"),
        position_generation=1,
        client_order_id=os.environ.get("R81_CLIENT", "client-r81"),
        strategy_name="r81",
        stop_loss="1.09000",
        take_profit="1.12000",
        entry_reference="decision-r81",
        atr_at_entry_pips="8",
    )


def _close() -> None:
    pos = positions.get("EUR_USD")
    if pos is None:
        print("refused=position_absent")
        return
    operation = asyncio.run(run_guarded_live_close(pos, reason="r81"))
    print(f"close_state={operation.confirmation_state}")
    print(f"close_error={operation.error_classification}")


def _entry() -> None:
    try:
        permit = _reserve()
    except JournalUnavailable as exc:
        print(f"refused={exc.reason}")
        return
    try:
        _place_market_order_open_sync(
            "EUR_USD",
            1000,
            "BUY",
            permit.client_order_id,
            1.09,
            1.12,
            mint_live_quote("EUR_USD"),
            entry_permit=permit,
        )
    except (EntryGuardRefusal, CloseGuardRefusal, JournalUnavailable, RuntimeError, TimeoutError) as exc:
        print(f"refused={getattr(exc, 'reason', type(exc).__name__)}")
        return
    print("submitted")


def _abandoned(die: bool) -> int:
    journal = os.environ["R81_JOURNAL"]
    lock = RecoveryOwnerLock(journal)
    if not lock.try_acquire():
        print("lock_failed")
        return 1
    token = uuid.uuid4().hex
    connection = sqlite3.connect(journal, isolation_level=None)
    connection.execute(
        """
        INSERT INTO recovery_runs (
            run_id, state, owner_token, created_at, updated_at, fencing_epoch,
            owner_pid, process_start, boot_id, lock_identity
        ) VALUES ('RUN-R81', 'RECOVERY_IN_PROGRESS', ?, 't', 't', 1, ?, ?, ?, ?)
        """,
        (token, os.getpid(), current_process_start(), host_boot_id(), lock_identity(journal)),
    )
    connection.close()
    status = Path(os.environ["R81_STATUS"])
    status.write_text(f"run_id=RUN-R81\nowner_token={token}\n", encoding="utf-8")
    Path(os.environ["R81_ENTERED"]).write_text("entered", encoding="utf-8")
    if die:
        os._exit(0)
    deadline = time.time() + 15
    while Path(os.environ["R81_RELEASE"]).read_text(encoding="utf-8") != "go":
        if time.time() > deadline:
            lock.release()
            print("timeout")
            return 1
        time.sleep(0.02)
    lock.release()
    print("released")
    return 0


def main() -> int:
    mode = sys.argv[1]
    os.environ["CLOSE_JOURNAL_PATH"] = os.environ["R81_JOURNAL"]
    os.environ["CLOSE_JOURNAL_BUSY_MS"] = "300"
    os.environ["EXECUTION_MODE"] = "paper_broker"
    os.environ["OANDA_MAX_RETRIES"] = "1"
    os.environ["OANDA_MAX_REQUESTS_PER_SEC"] = "120"
    config_mod.Config.OANDA_ACCOUNT_ID = ACCOUNT
    reset_oanda_rate_limiter_for_tests()
    live_safety.assert_new_live_exposure_allowed = lambda **kwargs: None
    oanda_client._api = RecordingAPI()
    _install_slot_barrier()
    if mode == "abandoned-hold":
        return _abandoned(False)
    if mode == "abandoned-die":
        return _abandoned(True)
    if mode == "entry-owner":
        _startup("COMPLETE_EMPTY")
        _entry()
        return 0
    if mode == "close-owner":
        _startup("durable")
        _close()
        return 0
    if mode == "stale-entry":
        _startup("COMPLETE_EMPTY")
        _signal_and_wait()
        _entry()
        return 0
    if mode == "stale-close":
        _startup("durable")
        _signal_and_wait()
        _close()
        return 0
    if mode == "restart-entry":
        _startup(os.environ.get("R81_SNAPSHOT", "COMPLETE_EMPTY"))
        _entry()
        return 0
    if mode == "restart-close":
        _startup(os.environ.get("R81_SNAPSHOT", "durable"))
        row = active_journal()._conn.execute(
            "SELECT confirmation_state, network_permit FROM close_operations ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        if row is not None:
            print(f"durable_close={row['confirmation_state']}")
            print(f"network_permit={row['network_permit']}")
        _close()
        return 0
    print("unknown_mode")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"worker_error={type(exc).__name__}:{exc}")
        raise SystemExit(1)

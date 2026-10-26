"""R.83 post-commit workers. Isolation is imported before operational modules."""

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
from forex_bot.close_journal import account_binding, active_journal  # noqa: E402
from forex_bot.entry_journal import begin_entry_submission  # noqa: E402
from forex_bot.market_provenance import mint_live_quote  # noqa: E402
from forex_bot.oanda_exec import _place_market_order_open_sync  # noqa: E402
from forex_bot.position_recovery import durable_positions, persist_bot_position  # noqa: E402
from forex_bot.positions import Position, position_management_permitted, positions  # noqa: E402
from forex_bot.startup_recovery import execute_startup_sequence, live_management_permitted  # noqa: E402
import forex_bot.config as config_mod  # noqa: E402
import forex_bot.entry_capture as entry_capture  # noqa: E402
import forex_bot.live_safety as live_safety  # noqa: E402
import forex_bot.startup_recovery as recovery_mod  # noqa: E402

ACCOUNT = "001-002-0000001-003"
WRITES = {"OrderCreate", "PositionClose"}


class RecordingAPI:
    def __init__(self, recorder: str, partial: bool = False) -> None:
        self.recorder = recorder
        self.partial = partial
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
            units = "400" if self.partial else "1000"
            return {
                "longOrderFillTransaction": {
                    "id": "TX-CLOSE",
                    "type": "ORDER_FILL",
                    "instrument": "EUR_USD",
                    "units": f"-{units}",
                }
            }
        if name == "TransactionDetails":
            units = "400" if self.partial else "1000"
            return {
                "transaction": {
                    "id": "TX-CLOSE",
                    "type": "ORDER_FILL",
                    "accountID": ACCOUNT,
                    "instrument": "EUR_USD",
                    "units": f"-{units}",
                    "tradesClosed": [{"tradeID": "T1", "units": units}],
                }
            }
        if name == "OrderCreate":
            data = getattr(request_obj, "data", {}) or {}
            order = data.get("order") if isinstance(data, dict) else {}
            client = str(((order or {}).get("clientExtensions") or {}).get("id") or "")
            return {
                "orderCreateTransaction": {"id": "O-R83", "accountID": ACCOUNT},
                "orderFillTransaction": {
                    "id": "F-R83",
                    "type": "ORDER_FILL",
                    "accountID": ACCOUNT,
                    "instrument": "EUR_USD",
                    "units": "1000",
                    "price": "1.10000",
                    "orderID": "O-R83",
                    "tradeOpened": {"tradeID": "T-R83", "units": "1000", "price": "1.10000"},
                    "clientExtensions": {"id": client},
                },
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
    if mode == "conflict-open":
        trade["units"] = "1000"
    return {"snapshot": "COMPLETE", "trades": [trade]}


def _print_recovery(report: dict) -> None:
    resident = positions.get("EUR_USD")
    print(f"state={report.get('state')}")
    print(f"management={int(live_management_permitted())}")
    print(f"in_book={int(resident is not None)}")
    print(f"manageable={int(position_management_permitted(resident))}")
    if resident is not None:
        print(f"units={resident.units}")
        print(f"trade={resident.broker_trade_ids}")
        print(f"direction={resident.direction}")
    journal = active_journal()
    entry = journal._conn.execute(
        "SELECT outcome, network_permit, client_order_id, broker_trade_id FROM entry_operations ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    if entry is not None:
        print(f"entry_outcome={entry['outcome']}")
        print(f"entry_permit={int(entry['network_permit'])}")
        print(f"entry_trade={entry['broker_trade_id']}")
    close = journal._conn.execute(
        "SELECT confirmation_state, network_permit, confirmed_units, remaining_units FROM close_operations ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    if close is not None:
        print(f"close_state={close['confirmation_state']}")
        print(f"close_permit={int(close['network_permit'])}")
        print(f"confirmed={close['confirmed_units']}")
        print(f"remaining={close['remaining_units']}")
    ratchet = journal._conn.execute(
        "SELECT profit_protection_exit_pips, units, trade_id FROM managed_positions ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    if ratchet is not None:
        print(f"durable_units={ratchet['units']}")
        print(f"durable_trade={ratchet['trade_id']}")
        print(f"ratchet={ratchet['profit_protection_exit_pips']}")
    epoch = journal._conn.execute("SELECT fencing_epoch FROM recovery_authority WHERE id = 1").fetchone()
    print(f"epoch={epoch['fencing_epoch'] if epoch else 'missing'}")
    for item in report.get("decisions") or []:
        print(f"decision={item.get('state')}:{item.get('reason')}")


def main() -> int:
    mode = sys.argv[1]
    os.environ["CLOSE_JOURNAL_PATH"] = os.environ["R83_JOURNAL"]
    os.environ["CLOSE_JOURNAL_BUSY_MS"] = "300"
    os.environ["EXECUTION_MODE"] = "paper_broker"
    os.environ["OANDA_MAX_RETRIES"] = "1"
    os.environ["OANDA_MAX_REQUESTS_PER_SEC"] = "120"
    config_mod.Config.OANDA_ACCOUNT_ID = ACCOUNT
    live_safety.assert_new_live_exposure_allowed = lambda **kwargs: None
    partial = mode.startswith("partial")
    oanda_client._api = RecordingAPI(os.environ["R83_RECORDER"], partial=partial)
    if mode == "successor":
        report = execute_startup_sequence(_view(os.environ.get("R83_VIEW", "match")))
        _print_recovery(report)
        if os.environ.get("R83_CYCLE") == "1":
            from forex_bot import bot_loop

            asyncio.run(bot_loop._execute_bot_cycle(["EUR_USD"]))
            print("cycle=1")
        return 0
    report = execute_startup_sequence({"snapshot": "COMPLETE_EMPTY", "trades": []})
    print(f"startup={report.get('state')}")
    binding = account_binding(ACCOUNT)
    if mode.startswith("entry"):
        permit = begin_entry_submission(
            account_binding_value=binding,
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            position_instance_id="INST-R83",
            position_generation=1,
            client_order_id="client-r83",
            strategy_name="r83",
            stop_loss="1.05",
            take_profit="1.20",
            entry_reference="r83",
            atr_at_entry_pips="8",
        )
        if mode == "entry-fence":
            real = recovery_mod.recovery_fence_allows_publication

            def wrapped() -> bool:
                _wait(os.environ["R83_ENTERED"], os.environ["R83_RELEASE"])
                return real()

            recovery_mod.recovery_fence_allows_publication = wrapped
        if mode == "entry-memory":
            book = entry_capture.positions

            class Barrier(dict):
                def __setitem__(self, key, value) -> None:
                    _wait(os.environ["R83_ENTERED"], os.environ["R83_RELEASE"])
                    super().__setitem__(key, value)

            entry_capture.positions = Barrier(book)
        _place_market_order_open_sync(
            "EUR_USD",
            1000,
            "BUY",
            permit.client_order_id,
            1.05,
            1.2,
            mint_live_quote("EUR_USD"),
            entry_permit=permit,
        )
        print(f"published={int('EUR_USD' in positions)}")
        return 0
    pos = Position(
        symbol="EUR_USD",
        direction="BUY",
        units=1000.0,
        entry_price=1.1,
        stop_loss=1.05,
        take_profit=1.2,
        open_time=1.0,
        strategy_name="r83",
        rl_state="held",
        execution_kind="live",
        broker_trade_ids="T1",
        position_instance_id="INST-CLOSE",
        position_generation=1,
        max_profit_pips=0.0,
        profit_protection_active=False,
        min_profit_pips=0.0,
        max_adverse_pips=0.0,
        profit_protection_exit_pips=40.0,
    )
    persist_bot_position(pos, binding)
    positions["EUR_USD"] = pos
    asyncio.run(run_guarded_live_close(positions["EUR_USD"], reason="r83"))
    _wait(os.environ["R83_ENTERED"], os.environ["R83_RELEASE"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"worker_error={type(exc).__name__}:{exc}")
        raise SystemExit(1)

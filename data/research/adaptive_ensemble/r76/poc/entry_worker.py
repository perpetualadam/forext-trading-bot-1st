"""Subprocess worker for the R.76 entry fence. Synthetic recorder only."""

from __future__ import annotations

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
from forex_bot.close_journal import JournalUnavailable, account_binding  # noqa: E402
from forex_bot.entry_journal import begin_entry_submission  # noqa: E402
from forex_bot.market_provenance import mint_live_quote  # noqa: E402
from forex_bot.oanda_exec import _place_market_order_open_sync  # noqa: E402
from forex_bot.oanda_rate_limit import reset_oanda_rate_limiter_for_tests  # noqa: E402
from forex_bot.startup_recovery import execute_startup_sequence  # noqa: E402
import forex_bot.config as config_mod  # noqa: E402
import forex_bot.live_safety as live_safety  # noqa: E402

ACCOUNT = "001-002-0000001-003"


class RecordingAPI:
    def request(self, request_obj):
        name = type(request_obj).__name__
        if name != "OrderCreate":
            raise isolation.IsolationBreach(name)
        entered = os.environ.get("R76_ENTERED", "")
        release = os.environ.get("R76_RELEASE", "")
        if entered:
            Path(entered).write_text("entered", encoding="utf-8")
            deadline = time.time() + 8
            while Path(release).read_text(encoding="utf-8") != "go":
                if time.time() > deadline:
                    raise TimeoutError("release barrier")
                time.sleep(0.01)
        connection = sqlite3.connect(os.environ["R76_RECORDER"], timeout=5, isolation_level=None)
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("INSERT INTO submissions (instrument) VALUES (?)", ("EUR_USD",))
        connection.execute("COMMIT")
        connection.close()
        client = os.environ["R76_CLIENT"]
        return {
            "orderCreateTransaction": {"id": "O-ORDER", "accountID": ACCOUNT},
            "orderFillTransaction": {
                "id": "F-1",
                "type": "ORDER_FILL",
                "accountID": ACCOUNT,
                "instrument": "EUR_USD",
                "units": "1000",
                "price": "1.10000",
                "orderID": "O-ORDER",
                "tradeOpened": {"tradeID": "T-TRADE", "units": "1000", "price": "1.10000"},
                "clientExtensions": {"id": client},
            },
        }


def main() -> int:
    mode = sys.argv[1]
    os.environ["OANDA_MAX_RETRIES"] = "1"
    os.environ["OANDA_MAX_REQUESTS_PER_SEC"] = "120"
    os.environ["EXECUTION_MODE"] = "paper_broker"
    config_mod.Config.OANDA_ACCOUNT_ID = ACCOUNT
    reset_oanda_rate_limiter_for_tests()
    if mode == "recover":
        report = execute_startup_sequence(
            {
                "snapshot": "COMPLETE_EMPTY",
                "trades": [],
            }
        )
        print(report["state"])
        print(report.get("reason", ""))
        return 0
    live_safety.assert_new_live_exposure_allowed = lambda **kwargs: None
    oanda_client._api = RecordingAPI()
    try:
        permit = begin_entry_submission(
            account_binding_value=account_binding(ACCOUNT),
            instrument="EUR_USD",
            direction="BUY",
            requested_units=Decimal("1000"),
            position_instance_id=os.environ.get("R76_INSTANCE", "instance-a"),
            position_generation=1,
            client_order_id=os.environ["R76_CLIENT"],
            strategy_name="r76",
            stop_loss="1.09000",
            take_profit="1.12000",
            entry_reference="decision-1",
            atr_at_entry_pips="8",
        )
        _place_market_order_open_sync(
            "EUR_USD",
            1000,
            "BUY",
            os.environ["R76_CLIENT"],
            1.09,
            1.12,
            mint_live_quote("EUR_USD"),
            entry_permit=permit,
        )
    except (JournalUnavailable, isolation.IsolationBreach, RuntimeError, TimeoutError) as exc:
        print(type(exc).__name__)
        print(getattr(exc, "reason", ""))
        return 0
    print("submitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

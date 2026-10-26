"""Subprocess worker for R.77 client-id and repair fences. Synthetic journal only."""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
R69 = ROOT / "data" / "research" / "adaptive_ensemble" / "r69" / "poc"
sys.path.insert(0, str(R69))
sys.path.insert(0, str(ROOT))

import isolation  # noqa: E402

from forex_bot.close_journal import JournalUnavailable, account_binding  # noqa: E402
from forex_bot.entry_journal import begin_entry_submission  # noqa: E402
from forex_bot.recovery_repair import (  # noqa: E402
    ProcessLivenessEvidence,
    RepairAuthorisation,
    repair_abandoned_recovery,
)

ACCOUNT = "001-002-0000001-003"


def main() -> int:
    os.environ["CLOSE_JOURNAL_PATH"] = os.environ["R77_JOURNAL"]
    os.environ["CLOSE_JOURNAL_BUSY_MS"] = "300"
    mode = sys.argv[1]
    if mode == "reserve":
        try:
            begin_entry_submission(
                account_binding_value=account_binding(ACCOUNT),
                instrument="EUR_USD",
                direction="BUY",
                requested_units=Decimal("1000"),
                position_instance_id=os.environ.get("R77_INSTANCE", "INST-1"),
                position_generation=1,
                client_order_id=os.environ["R77_CLIENT"],
                strategy_name="r77",
                stop_loss="1.09000",
                take_profit="1.12000",
                entry_reference="decision-1",
                atr_at_entry_pips="8",
            )
        except JournalUnavailable as exc:
            print(exc.reason)
            return 0
        print("accepted")
        return 0
    result = repair_abandoned_recovery(
        RepairAuthorisation(
            operator_acknowledged=True,
            acknowledgement="operator confirms the recovery owner has exited",
            account_binding=account_binding(ACCOUNT),
            journal_path=os.environ["R77_JOURNAL"],
            target_run_id=os.environ["R77_RUN"],
            liveness=ProcessLivenessEvidence(
                "inactive",
                "owner_token_and_exit_observation",
                os.environ["R77_OWNER"],
            ),
        )
    )
    print(result["result"] + " " + result["reason"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"worker_error {type(exc).__name__} {exc}")
        raise SystemExit(1)

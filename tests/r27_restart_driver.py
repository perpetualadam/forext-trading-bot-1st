"""One-shot R.27 restart process. Inert broker and no production launcher."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

ACCOUNT = "101-004-1435156-001"
CURRENCY = "USD"
DAY = "2026-01-07"
OPEN = "2026-01-07T12:00:00+00:00"


def seed_state(path: Path, *, peak: float, baseline: float, realised: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "schema_version": 1,
        "peak_equity": peak,
        "day_baselines": {DAY: baseline},
        "realised_by_day": {DAY: realised},
        "account_id": ACCOUNT,
        "currency": CURRENCY,
        "revision": 1,
        "events": {},
        "exposure_positions": [],
        "exposure_orders": [],
        "reconciliation": {
            "status": "synthetic_offline",
            "account_id": ACCOUNT,
            "currency": CURRENCY,
            "snapshot_id": "synthetic-seed",
            "as_of": OPEN,
            "equity_source": "synthetic_seed",
            "sequence_evidence": "absent",
            "last_sequence": None,
        },
    }
    path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")


def _barriers() -> None:
    class _Blocked(socket.socket):
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise RuntimeError("R27_NETWORK_BLOCKED")

    def _blocked(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("R27_DNS_BLOCKED")

    socket.socket = _Blocked  # type: ignore[misc]
    socket.getaddrinfo = _blocked  # type: ignore[assignment]
    socket.gethostbyname = _blocked  # type: ignore[assignment]
    socket.create_connection = _blocked  # type: ignore[assignment]
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
    sys.modules["dotenv"] = dotenv


def _summary(nav: str, *, orders: list[dict] | None = None, observed_at: str = OPEN) -> dict:
    return {
        "observed_at": observed_at,
        "account": {
            "id": ACCOUNT,
            "currency": CURRENCY,
            "NAV": nav,
            "balance": nav,
            "unrealizedPL": "0.0000",
            "positions": [],
            "orders": orders or [],
        },
    }


def _fill(amount: str, event_id: str = "1") -> dict:
    return {
        "lastTransactionID": event_id,
        "transactions": [
            {
                "orderFillTransaction": {
                    "id": event_id,
                    "pl": amount,
                    "price": "1.10000",
                    "units": "1",
                    "time": "2026-01-07T11:00:00+00:00",
                }
            }
        ],
    }


def main() -> int:
    _barriers()
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=("persist", "evaluate", "replay", "incomplete"))
    parser.add_argument("--scenario", required=True, choices=("loss", "drawdown", "exposure", "duplicate"))
    parser.add_argument("--state", required=True)
    parser.add_argument("--balance", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(root / "data" / "research" / "adaptive_ensemble" / "r27" / "synthetic_live_safety_state.json")
    os.environ["RISK_STATE_PATH"] = args.state
    os.environ["RISK_MAX_DAILY_LOSS_PCT"] = "0.02"
    os.environ["RISK_MAX_DRAWDOWN_PCT"] = "0.05"
    os.environ["RISK_MAX_TOTAL_EXPOSURE_PCT"] = "20" if args.scenario == "exposure" else "1000"
    os.environ["RISK_ACCOUNT_ID"] = ACCOUNT
    os.environ["RISK_ACCOUNT_CURRENCY"] = CURRENCY
    from forex_bot.bot_loop import IterationDependencies, evaluate_one_instrument_iteration

    summary = None
    transactions = None
    if args.role != "evaluate":
        if args.scenario == "loss":
            summary = _summary("10000.0000")
            transactions = _fill("-200.0000")
        elif args.scenario == "drawdown":
            summary = _summary("11000.0000", observed_at="2026-01-07T11:59:00+00:00")
        elif args.scenario == "exposure":
            summary = _summary(
                "10000.0000",
                orders=[
                    {
                        "id": "204",
                        "instrument": "GBP_USD",
                        "state": "PENDING",
                        "units": "-1000000",
                        "price": "1.27000",
                        "type": "LIMIT",
                    }
                ],
            )
        elif args.scenario == "duplicate":
            summary = _summary("10000.0000")
            transactions = _fill("-50.0000")
        if args.role == "incomplete":
            transactions = {
                "lastTransactionID": "4",
                "transactions": _fill("-50.0000")["transactions"],
            }
    opened = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
    import importlib.util

    spec = importlib.util.spec_from_file_location("r12_fakes", root / "tests" / "r12_fakes.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    broker = module.FakeBroker("filled")
    result = evaluate_one_instrument_iteration(
        "EUR_USD",
        IterationDependencies(
            candles=[
                {
                    "open": 1.1,
                    "high": 1.1002,
                    "low": 1.0998,
                    "close": 1.1,
                    "time": "2026-01-07T11:58:00+00:00" if index == 49 else f"2026-01-07T10:{index % 60:02d}:00+00:00",
                }
                for index in range(50)
            ],
            balance=float(args.balance),
            account_present=True,
            account_context="isolated_test",
            account_payload={"id": ACCOUNT},
            simulation=True,
            now=opened,
            quote_as_of=opened,
            account_as_of=opened,
            unrealised=0.0,
            price=1.1,
            bid=1.09995,
            ask=1.10005,
            stop_distance=0.001,
            stop_loss=1.099,
            take_profit=1.102,
            broker=broker,
            strategy_name="scalp",
            strategy_known=True,
            strategy_active=True,
            strategy_authorised=True,
            safety_initialised=True,
            vote={"allow": True, "direction": "BUY", "confidence": 0.8},
            expected_account_id=ACCOUNT,
            expected_account_currency=CURRENCY,
            oanda_summary=summary,
            oanda_transactions=transactions,
        ),
    )
    state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "pid": os.getpid(),
                "role": args.role,
                "exit_pid": os.getpid(),
                "blocked_by": result.get("blocked_by") or "",
                "broker_requests": broker.request_count,
                "reservation_attempted": bool(result.get("details", {}).get("reservation_attempted")),
                "production_eligible": result.get("production_eligible"),
                "realised": state["realised_by_day"][DAY],
                "peak_equity": state["peak_equity"],
                "account_id": state.get("account_id"),
                "event_ids": sorted(state.get("events") or {}),
                "exposure_order_ids": [item.get("id") for item in state.get("exposure_orders") or []],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

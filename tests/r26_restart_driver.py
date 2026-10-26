"""One-shot R.26 restart process. Inert broker and no production launcher."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

ACCOUNT = "ACCT-R26"
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
            raise RuntimeError("R26_NETWORK_BLOCKED")

    def _blocked(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("R26_DNS_BLOCKED")

    socket.socket = _Blocked  # type: ignore[misc]
    socket.getaddrinfo = _blocked  # type: ignore[assignment]
    socket.gethostbyname = _blocked  # type: ignore[assignment]
    socket.create_connection = _blocked  # type: ignore[assignment]
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
    sys.modules["dotenv"] = dotenv


def _snapshot(nav: float, *, orders: list[dict] | None = None, event_amount: float | None = None) -> tuple[dict, list[dict]]:
    snapshot = {
        "provenance": "injected_synthetic",
        "id": ACCOUNT,
        "currency": CURRENCY,
        "snapshot_id": f"snap-{nav}",
        "as_of": OPEN,
        "NAV": nav,
        "balance": nav,
        "unrealised": 0.0,
        "positions": [],
        "orders": orders or [],
    }
    events = []
    if event_amount is not None:
        events.append(
            {
                "id": "trade-restart",
                "kind": "trade_pl",
                "amount": event_amount,
                "time": "2026-01-07T11:00:00+00:00",
            }
        )
    return snapshot, events


def _dependencies(balance: float, snapshot: dict | None, events: list[dict] | None):
    from forex_bot.bot_loop import IterationDependencies

    opened = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
    return IterationDependencies(
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
        balance=balance,
        account_present=True,
        account_context="isolated_test",
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
        broker=_broker(),
        strategy_name="scalp",
        strategy_known=True,
        strategy_active=True,
        strategy_authorised=True,
        safety_initialised=True,
        vote={"allow": True, "direction": "BUY", "confidence": 0.8},
        account_payload={"id": ACCOUNT},
        expected_account_id=ACCOUNT,
        expected_account_currency=CURRENCY,
        broker_snapshot=snapshot,
        broker_events=tuple(events or []),
    )


def _broker():
    import importlib.util

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("r12_fakes", root / "tests" / "r12_fakes.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module.FakeBroker("filled")


def main() -> int:
    _barriers()
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=("persist", "evaluate", "duplicate"))
    parser.add_argument("--scenario", required=True, choices=("loss", "drawdown", "exposure", "duplicate"))
    parser.add_argument("--state", required=True)
    parser.add_argument("--balance", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(root / "data" / "research" / "adaptive_ensemble" / "r26" / "synthetic_live_safety_state.json")
    os.environ["RISK_STATE_PATH"] = args.state
    os.environ["RISK_MAX_DAILY_LOSS_PCT"] = "0.02"
    os.environ["RISK_MAX_DRAWDOWN_PCT"] = "0.05"
    os.environ["RISK_MAX_TOTAL_EXPOSURE_PCT"] = "20" if args.scenario == "exposure" else "1000"
    os.environ["RISK_ACCOUNT_ID"] = ACCOUNT
    os.environ["RISK_ACCOUNT_CURRENCY"] = CURRENCY
    from forex_bot.bot_loop import evaluate_one_instrument_iteration

    orders = None
    event_amount = None
    nav = float(args.balance)
    if args.scenario == "loss":
        nav = 10000.0
        event_amount = -200.0
    elif args.scenario == "drawdown":
        nav = 11000.0
    elif args.scenario == "exposure":
        nav = 10000.0
        orders = [{"id": "pend-restart", "symbol": "GBP_USD", "status": "PENDING", "units": 1_000_000, "price": 1.27}]
    elif args.scenario == "duplicate":
        nav = 10000.0
        event_amount = -50.0
    snapshot, events = _snapshot(nav, orders=orders, event_amount=event_amount)
    if args.role == "evaluate":
        snapshot, events = None, None
    broker_balance = float(args.balance)
    dependencies = _dependencies(broker_balance, snapshot, events)
    result = evaluate_one_instrument_iteration("EUR_USD", dependencies)
    state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    payload = {
        "pid": os.getpid(),
        "role": args.role,
        "exit_pid": os.getpid(),
        "blocked_by": result.get("blocked_by") or "",
        "broker_requests": dependencies.broker.request_count,
        "reservation_attempted": bool(result.get("details", {}).get("reservation_attempted")),
        "production_eligible": result.get("production_eligible"),
        "realised": state["realised_by_day"][DAY],
        "peak_equity": state["peak_equity"],
        "event_ids": sorted(state.get("events") or {}),
        "exposure_order_ids": [item.get("id") for item in state.get("exposure_orders") or []],
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

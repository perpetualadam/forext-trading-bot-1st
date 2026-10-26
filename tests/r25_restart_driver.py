"""One-shot R.25 restart process. Inert broker and no production launcher."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import types
from datetime import datetime, timezone
from pathlib import Path


def _barriers() -> None:
    class _Blocked(socket.socket):
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise RuntimeError("R25_NETWORK_BLOCKED")

    def _blocked(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("R25_DNS_BLOCKED")

    socket.socket = _Blocked  # type: ignore[misc]
    socket.getaddrinfo = _blocked  # type: ignore[assignment]
    socket.gethostbyname = _blocked  # type: ignore[assignment]
    socket.create_connection = _blocked  # type: ignore[assignment]
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
    sys.modules["dotenv"] = dotenv


def main() -> int:
    _barriers()
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=("record-loss", "evaluate"))
    parser.add_argument("--state", required=True)
    parser.add_argument("--balance", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(root / "data" / "research" / "adaptive_ensemble" / "r25" / "synthetic_live_safety_state.json")
    os.environ["RISK_STATE_PATH"] = args.state
    os.environ["RISK_MAX_DAILY_LOSS_PCT"] = "0.02"
    os.environ["RISK_MAX_DRAWDOWN_PCT"] = "0.05"
    os.environ["RISK_MAX_TOTAL_EXPOSURE_PCT"] = "1000"
    from forex_bot.bot_loop import IterationDependencies, evaluate_one_instrument_iteration
    from forex_bot.execution_risk import apply_realised_delta

    payload: dict[str, object] = {"pid": os.getpid(), "role": args.role, "exit_pid": os.getpid()}
    if args.role == "record-loss":
        reason = apply_realised_delta("2026-01-07", -200.0, path=Path(args.state))
        payload["recorded"] = reason is None
        payload["blocked_by"] = reason or ""
        payload["broker_requests"] = 0
        payload["reservation_attempted"] = False
        print(json.dumps(payload))
        return 0 if reason is None else 1

    opened = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
    spec_path = root / "tests" / "r12_fakes.py"
    import importlib.util

    spec = importlib.util.spec_from_file_location("r12_fakes", spec_path)
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
        ),
    )
    payload.update(
        {
            "blocked_by": result.get("blocked_by"),
            "broker_requests": broker.request_count,
            "reservation_attempted": bool((result.get("details") or {}).get("reservation_attempted")),
            "production_eligible": result.get("production_eligible"),
        }
    )
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

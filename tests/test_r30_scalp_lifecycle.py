"""Offline R.30 scalp lifecycle checks. No broker, database, or live loop."""

from __future__ import annotations

import importlib.util
import json
import os
import socket
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd


class _BlockedSocket(socket.socket):
    def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("R30_NETWORK_BLOCKED")


def _blocked_name(*_args, **_kwargs):  # noqa: ANN002, ANN003
    raise RuntimeError("R30_DNS_BLOCKED")


socket.socket = _BlockedSocket  # type: ignore[misc]
socket.getaddrinfo = _blocked_name  # type: ignore[assignment]
socket.gethostbyname = _blocked_name  # type: ignore[assignment]
socket.create_connection = _blocked_name  # type: ignore[assignment]
_dotenv = types.ModuleType("dotenv")
_dotenv.load_dotenv = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
sys.modules["dotenv"] = _dotenv

ROOT = Path(__file__).resolve().parents[1]
R30 = ROOT / "data" / "research" / "adaptive_ensemble" / "r30"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R30 / "synthetic_live_safety_state.json")
sys.path.insert(0, str(ROOT))

from forex_bot.bot_loop import IterationDependencies, evaluate_one_instrument_iteration  # noqa: E402
from forex_bot.database import (  # noqa: E402
    note_blocking_reservation,
    reset_order_intent_gate_for_tests,
    restore_unresolved_intent,
)
from forex_bot.orders import reset_orders_for_tests  # noqa: E402
from forex_bot.positions import close_position, positions  # noqa: E402
from forex_bot.shadow.signals import build_feature_pack, signal_from_arrays  # noqa: E402
from forex_bot.strategy_meta import strategies  # noqa: E402

SPEC = importlib.util.spec_from_file_location("r30_simulator", R30 / "simulator.py")
SIM = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(SIM)

OPEN = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
DAY = "2026-01-07"
ACCOUNT = "synthetic-r30"
START = datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc)


def _bars(prices: list[tuple[float, float, float, float]], start: datetime = START, step: int = 5) -> pd.DataFrame:
    rows = []
    for index, (bid_open, bid_high, bid_low, bid_close) in enumerate(prices):
        ask_open = bid_open + 0.0001
        ask_high = bid_high + 0.0001
        ask_low = bid_low + 0.0001
        ask_close = bid_close + 0.0001
        rows.append(
            {
                "_time": start + timedelta(minutes=step * index),
                "bid_open": bid_open,
                "bid_high": bid_high,
                "bid_low": bid_low,
                "bid_close": bid_close,
                "ask_open": ask_open,
                "ask_high": ask_high,
                "ask_low": ask_low,
                "ask_close": ask_close,
            }
        )
    return pd.DataFrame(rows)


def _flat(n: int = 4, price: float = 1.10) -> pd.DataFrame:
    return _bars([(price, price + 0.0002, price - 0.0002, price) for _ in range(n)])


def _broker():
    spec = importlib.util.spec_from_file_location("r12_fakes", ROOT / "tests" / "r12_fakes.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module.FakeBroker("filled")


def _seed(name: str, *, peak: float = 10000.0, realised: float = 0.0) -> None:
    path = R30 / "states" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "peak_equity": peak,
                "day_baselines": {DAY: 10000.0},
                "realised_by_day": {DAY: realised},
                "account_id": ACCOUNT,
                "currency": "USD",
                "revision": 1,
                "events": {},
                "exposure_positions": [],
                "exposure_orders": [],
                "reconciliation": {
                    "status": "synthetic_offline",
                    "account_id": ACCOUNT,
                    "currency": "USD",
                    "snapshot_id": "synthetic-seed",
                    "as_of": OPEN.isoformat(),
                    "equity_source": "synthetic_seed",
                    "sequence_evidence": "absent",
                    "last_sequence": None,
                },
            }
        ),
        encoding="utf-8",
    )
    os.environ["RISK_STATE_PATH"] = str(path)
    os.environ["RISK_ACCOUNT_ID"] = ACCOUNT
    os.environ["RISK_ACCOUNT_CURRENCY"] = "USD"
    os.environ["RISK_MAX_DAILY_LOSS_PCT"] = "0.02"
    os.environ["RISK_MAX_DRAWDOWN_PCT"] = "0.05"
    os.environ["RISK_MAX_TOTAL_EXPOSURE_PCT"] = "1000"


def _snap(**extra: object) -> dict:
    body = {
        "provenance": "injected_synthetic",
        "id": ACCOUNT,
        "currency": "USD",
        "snapshot_id": "r30-snap",
        "as_of": OPEN,
        "NAV": 10000.0,
        "balance": 10000.0,
        "unrealised": 0.0,
        "positions": [],
        "orders": [],
    }
    body.update(extra)
    return body


def _run(**overrides: object) -> dict:
    broker = overrides.pop("broker", None) or _broker()
    values: dict[str, object] = {
        "candles": [
            {
                "open": 1.1,
                "high": 1.1002,
                "low": 1.0998,
                "close": 1.1,
                "time": "2026-01-07T11:58:00+00:00" if index == 49 else f"2026-01-07T10:{index % 60:02d}:00+00:00",
            }
            for index in range(50)
        ],
        "balance": 10000.0,
        "account_present": True,
        "account_context": "isolated_test",
        "simulation": True,
        "now": OPEN,
        "quote_as_of": OPEN,
        "account_as_of": OPEN,
        "unrealised": 0.0,
        "price": 1.1,
        "bid": 1.09995,
        "ask": 1.10005,
        "stop_distance": 0.002,
        "stop_loss": 1.098,
        "take_profit": 1.104,
        "broker": broker,
        "strategy_name": "scalp",
        "strategy_known": True,
        "strategy_active": True,
        "strategy_authorised": True,
        "safety_initialised": True,
        "vote": {"allow": True, "direction": "BUY", "confidence": 0.8},
        "account_payload": {"id": ACCOUNT},
        "expected_account_id": ACCOUNT,
        "expected_account_currency": "USD",
        "broker_snapshot": _snap(),
    }
    values.update(overrides)
    result = evaluate_one_instrument_iteration("EUR_USD", IterationDependencies(**values))  # type: ignore[arg-type]
    result["broker_requests"] = broker.request_count
    result["broker"] = broker
    return result


def _blocked(result: dict, reason: str) -> bool:
    return (
        result["blocked_by"] == reason
        and result["broker_requests"] == 0
        and result["details"].get("reservation_attempted") is False
        and result["production_eligible"] is False
    )


def _clear() -> None:
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    for symbol in list(positions):
        close_position(symbol)


def setup_function() -> None:
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    _clear()
    for strategy in strategies.values():
        assert strategy.active is False
        assert strategy.authorised_for_live is False


def test_entry_events_suppress_repeated_direction() -> None:
    assert SIM.entry_events([None, "BUY", "BUY", "BUY", None, "BUY", "SELL", "SELL"]) == [1, 5, 6]


def test_next_bar_uses_the_quoted_side() -> None:
    frame = _flat()
    result = SIM.simulate(frame, [None, "BUY", "BUY", None])
    assert len(result["trades"]) == 1
    trade = result["trades"][0]
    assert trade["entry_index"] == 2
    assert trade["entry_price"] == frame.iloc[2]["ask_open"]
    assert trade["direction"] == "BUY"
    short = SIM.simulate(frame, [None, "SELL", "SELL", None])
    assert short["trades"][0]["entry_price"] == frame.iloc[2]["bid_open"]
    assert short["trades"][0]["exit_reason"] == "end_of_data"
    assert short["trades"][0]["exit_price"] == frame.iloc[-1]["ask_close"]


def test_repeated_state_does_not_pyramid_or_reenter() -> None:
    frame = _flat(5)
    result = SIM.simulate(frame, ["BUY", "BUY", "BUY", "BUY", "BUY"])
    assert len(result["trades"]) == 1
    assert result["trades"][0]["units"] == 50000.0


def test_reversal_exits_without_opening_the_other_side() -> None:
    frame = _flat()
    result = SIM.simulate(frame, ["BUY", "SELL", "SELL", None])
    assert len(result["trades"]) == 1
    assert result["trades"][0]["direction"] == "BUY"
    assert result["trades"][0]["exit_reason"] == "signal_reversal"
    assert result["trades"][0]["exit_price"] == frame.iloc[2]["bid_open"]


def test_stop_take_profit_and_ambiguous_bar() -> None:
    calm = _flat(3)
    stopped = SIM.simulate(calm, ["BUY", "BUY", "BUY"])
    assert stopped["trades"][0]["stop"] == stopped["trades"][0]["entry_price"] - 0.002
    assert stopped["trades"][0]["take_profit"] == stopped["trades"][0]["entry_price"] + 0.004
    prices = [
        (1.10, 1.1002, 1.0998, 1.10),
        (1.10, 1.1002, 1.0998, 1.10),
        (1.10, 1.1050, 1.0970, 1.1010),
    ]
    frame = _bars(prices)
    result = SIM.simulate(frame, ["BUY", "BUY", None])
    assert result["trades"][0]["exit_reason"] == "ambiguous_stop"
    assert result["trades"][0]["exit_price"] == result["trades"][0]["stop"]


def test_gap_uses_the_open_when_it_is_worse_than_the_stop() -> None:
    rows = [
        (1.10, 1.1002, 1.0998, 1.10),
        (1.10, 1.1002, 1.0998, 1.10),
        (1.0900, 1.0910, 1.0890, 1.0905),
    ]
    frame = _bars(rows)
    frame.loc[2, "_time"] = START + timedelta(hours=5)
    result = SIM.simulate(frame, ["BUY", "BUY", None])
    assert result["trades"][0]["exit_reason"] == "gap_exit"
    assert result["trades"][0]["exit_price"] == 1.0900
    assert result["trades"][0]["exit_price"] < result["trades"][0]["stop"]


def test_missing_bar_cancels_the_entry() -> None:
    frame = _bars(
        [
            (1.10, 1.1002, 1.0998, 1.10),
            (1.10, 1.1002, 1.0998, 1.10),
        ]
    )
    frame.loc[1, "_time"] = START + timedelta(minutes=10)
    result = SIM.simulate(frame, ["BUY", None])
    assert result["trades"] == []
    assert result["cancelled_entries"] == 1


def test_end_of_data_closes_on_the_exit_side() -> None:
    frame = _flat(3)
    result = SIM.simulate(frame, ["BUY", "BUY", "BUY"])
    trade = result["trades"][0]
    assert trade["exit_reason"] == "end_of_data"
    assert trade["exit_price"] == frame.iloc[-1]["bid_close"]
    assert trade["entry_price"] == frame.iloc[1]["ask_open"]


def test_session_and_invalid_size_block_entries() -> None:
    frame = _flat(2, price=1.10)
    frame["_time"] = [datetime(2026, 1, 7, 23, 0, tzinfo=timezone.utc), datetime(2026, 1, 7, 23, 5, tzinfo=timezone.utc)]
    assert SIM.simulate(frame, ["BUY", "BUY"])["trades"] == []
    assert SIM._size(0) == 0
    assert SIM._size(10000) == 50000
    assert SIM.STOP_DISTANCE == 0.002


def test_costs_do_not_add_the_spread_twice() -> None:
    frame = _flat(3)
    base = SIM.simulate(frame, ["BUY", "BUY", "BUY"], slippage=0.0)
    slipped = SIM.simulate(frame, ["BUY", "BUY", "BUY"], slippage=0.0001)
    assert slipped["trades"][0]["entry_price"] == base["trades"][0]["entry_price"] + 0.0001
    assert slipped["trades"][0]["exit_price"] == base["trades"][0]["exit_price"] - 0.0001
    assert slipped["trades"][0]["pnl"] < base["trades"][0]["pnl"]
    spread = float(frame.iloc[1]["ask_open"]) - float(frame.iloc[1]["bid_open"])
    assert abs((base["trades"][0]["entry_price"] - base["trades"][0]["entry_mid"]) - spread / 2) < 1e-12


def test_split_is_chronological_and_results_repeat() -> None:
    assert SIM.split_index(10) == 7
    frame = _flat(6)
    signals = ["BUY", "BUY", None, "SELL", "SELL", None]
    first = SIM.simulate(frame, signals)
    second = SIM.simulate(frame, signals)
    assert first["trades"] == second["trades"]
    summary = SIM.summarize(first, start=0, end=SIM.split_index(len(frame)))
    assert summary["trades"] == sum(trade["entry_index"] < 4 for trade in first["trades"])


def test_signal_prefix_matches_the_full_pack() -> None:
    rows = []
    for index in range(80):
        close = 1.10 + index * 0.0002
        rows.append((close, close + 0.0001, close - 0.0001, close))
    frame = _bars(rows)
    work = pd.DataFrame(
        {"open": frame["bid_open"], "high": frame["bid_high"], "low": frame["bid_low"], "close": frame["bid_close"]}
    )
    full = build_feature_pack(work, 50, 250)
    for index in (60, 79):
        partial = build_feature_pack(work.iloc[: index + 1], 50, 250)
        assert signal_from_arrays("scalp", index, full) == signal_from_arrays("scalp", index, partial)


def test_evaluate_blocks_and_dispatches_once() -> None:
    _seed("eligible")
    first = _run()
    assert first["blocked_by"] == ""
    assert first["broker_requests"] == 1
    assert first["production_eligible"] is False
    second = _run(broker=first["broker"])
    assert second["blocked_by"] == "position_already_open"
    assert second["broker_requests"] == 1
    _clear()
    cases = []
    _seed("stop")
    cases.append((_run(stop_distance=float("nan")), "sizing_input_invalid"))
    _seed("nav")
    cases.append((_run(broker_snapshot=_snap(NAV=None)), "broker_value_nonfinite"))
    _seed("loss", realised=-200.0)
    cases.append((_run(), "daily_realised_loss_limit"))
    _seed("drawdown", peak=11000.0)
    cases.append((_run(broker_snapshot=_snap(NAV=10450.0, balance=10450.0)), "max_drawdown_limit"))
    _seed("exposure")
    os.environ["RISK_MAX_TOTAL_EXPOSURE_PCT"] = "0.5"
    cases.append((_run(broker_snapshot=_snap(positions=[{"symbol": "EUR_USD", "units": 100000, "price": 1.1}])), "total_exposure_limit"))
    os.environ["RISK_MAX_TOTAL_EXPOSURE_PCT"] = "1000"
    _clear()
    _seed("reservation")
    note_blocking_reservation("EUR_USD", "r30-pending")
    cases.append((_run(), "active_reservation"))
    _clear()
    _seed("unresolved")
    restore_unresolved_intent("EUR_USD", "r30-unresolved")
    cases.append((_run(), "unresolved_intent"))
    _clear()
    _seed("pages")
    summary = {
        "account": {
            "id": ACCOUNT,
            "currency": "USD",
            "NAV": "10000",
            "balance": "10000",
            "unrealizedPL": "0",
            "lastTransactionID": "1",
            "positions": [],
            "orders": [],
        }
    }
    cases.append((_run(broker_snapshot=None, oanda_summary=summary, oanda_transactions={"pages": ["not-fetched"]}), "transaction_pages_incomplete"))
    for result, reason in cases:
        assert _blocked(result, reason), (reason, result["blocked_by"])
    assert all(item.active is False and item.authorised_for_live is False for item in strategies.values())

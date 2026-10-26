"""Offline R.31 screening checks. No broker, database, or historical ranking."""

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
        raise RuntimeError("R31_NETWORK_BLOCKED")


def _blocked_name(*_args, **_kwargs):  # noqa: ANN002, ANN003
    raise RuntimeError("R31_DNS_BLOCKED")


socket.socket = _BlockedSocket  # type: ignore[misc]
socket.getaddrinfo = _blocked_name  # type: ignore[assignment]
socket.gethostbyname = _blocked_name  # type: ignore[assignment]
socket.create_connection = _blocked_name  # type: ignore[assignment]
_dotenv = types.ModuleType("dotenv")
_dotenv.load_dotenv = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
sys.modules["dotenv"] = _dotenv

ROOT = Path(__file__).resolve().parents[1]
R31 = ROOT / "data" / "research" / "adaptive_ensemble" / "r31"
R30 = ROOT / "data" / "research" / "adaptive_ensemble" / "r30"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R31 / "synthetic_live_safety_state.json")
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

NAMES = ("scalp", "trend", "mean_reversion", "swing_trend", "swing_mean_reversion", "swing_breakout")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


SIM = _load(R30 / "simulator.py", "r30_simulator_review")
RANK = _load(R31 / "ranking.py", "r31_ranking")
OPEN = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
DAY = "2026-01-07"
ACCOUNT = "synthetic-r31"


def _bars(start: datetime, prices: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    rows = []
    for index, (bid_open, bid_high, bid_low, bid_close) in enumerate(prices):
        rows.append(
            {
                "_time": start + timedelta(minutes=5 * index),
                "bid_open": bid_open,
                "bid_high": bid_high,
                "bid_low": bid_low,
                "bid_close": bid_close,
                "ask_open": bid_open + 0.0001,
                "ask_high": bid_high + 0.0001,
                "ask_low": bid_low + 0.0001,
                "ask_close": bid_close + 0.0001,
            }
        )
    return pd.DataFrame(rows)


def _quiet(n: int, start: datetime, price: float = 1.10) -> pd.DataFrame:
    return _bars(start, [(price, price + 0.0002, price - 0.0002, price) for _ in range(n)])


def _broker():
    return _load(ROOT / "tests" / "r12_fakes.py", "r12_fakes_r31").FakeBroker("filled")


def _seed(name: str, *, peak: float = 10000.0, realised: float = 0.0) -> None:
    path = R31 / "states" / f"{name}.json"
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
        "snapshot_id": "r31-snap",
        "as_of": OPEN,
        "NAV": 10000.0,
        "balance": 10000.0,
        "unrealised": 0.0,
        "positions": [],
        "orders": [],
    }
    body.update(extra)
    return body


def _candles(count: int) -> list[dict[str, object]]:
    end = datetime(2026, 1, 7, 11, 58, tzinfo=timezone.utc)
    rows = []
    for index in range(count):
        stamp = end - timedelta(minutes=5 * (count - 1 - index))
        rows.append(
            {
                "open": 1.1,
                "high": 1.1002,
                "low": 1.0998,
                "close": 1.1,
                "time": stamp.isoformat(),
            }
        )
    return rows


def _run(strategy: str, **overrides: object) -> dict:
    broker = overrides.pop("broker", None) or _broker()
    candle_count = int(overrides.pop("candle_count", 100 if strategy.startswith("swing") else 50))
    values: dict[str, object] = {
        "candles": _candles(candle_count),
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
        "broker": broker,
        "strategy_name": strategy,
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
    _clear()
    for name in NAMES:
        assert strategies[name].active is False
        assert strategies[name].authorised_for_live is False


def test_cash_ledger_matches_the_quoted_fill() -> None:
    start = datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc)
    frame = _quiet(3, start)
    result = SIM.simulate(frame, ["BUY", "BUY", "BUY"])
    trade = result["trades"][0]
    expected = (1.10 - 1.1001) * 50000
    assert trade["entry_price"] == 1.1001
    assert trade["exit_price"] == 1.10
    assert abs(trade["pnl"] - expected) < 1e-9
    assert abs(result["ending_cash"] - (10000 + expected)) < 1e-9


def test_weekend_flatten_uses_the_friday_open() -> None:
    start = datetime(2026, 1, 9, 20, 30, tzinfo=timezone.utc)
    frame = _quiet(4, start)
    frame.loc[3, "bid_open"] = 1.0970
    result = SIM.simulate(frame, ["BUY", "BUY", "BUY", None])
    assert result["trades"][0]["exit_reason"] == "weekend_flatten"
    assert result["trades"][0]["exit_price"] == 1.0970


def test_take_profit_and_entry_bar_stop() -> None:
    start = datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc)
    target = _bars(
        start,
        [
            (1.10, 1.1002, 1.0998, 1.10),
            (1.10, 1.1002, 1.0998, 1.10),
            (1.1010, 1.1060, 1.1005, 1.1020),
        ],
    )
    taken = SIM.simulate(target, ["BUY", "BUY", None])
    assert taken["trades"][0]["exit_reason"] == "take_profit"
    assert taken["trades"][0]["exit_price"] == taken["trades"][0]["take_profit"]
    stopped = _bars(
        start,
        [
            (1.10, 1.1002, 1.0998, 1.10),
            (1.10, 1.1010, 1.0900, 1.0990),
        ],
    )
    hit = SIM.simulate(stopped, ["BUY", None])
    assert hit["trades"][0]["entry_index"] == 1
    assert hit["trades"][0]["exit_index"] == 1
    assert hit["trades"][0]["exit_reason"] == "stop"
    assert hit["trades"][0]["exit_price"] == hit["trades"][0]["stop"]


def test_short_reversal_exits_on_the_ask() -> None:
    start = datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc)
    frame = _quiet(4, start)
    result = SIM.simulate(frame, ["SELL", "BUY", "BUY", None])
    trade = result["trades"][0]
    assert trade["direction"] == "SELL"
    assert trade["entry_price"] == frame.iloc[1]["bid_open"]
    assert trade["exit_reason"] == "signal_reversal"
    assert trade["exit_price"] == frame.iloc[2]["ask_open"]
    assert len(result["trades"]) == 1


def test_strategy_signals_are_deterministic_and_causal() -> None:
    rows = []
    for index in range(160):
        close = 1.08 + (index % 17) * 0.0003
        rows.append({"open": close, "high": close + 0.0004, "low": close - 0.0004, "close": close})
    frame = pd.DataFrame(rows)
    for name, lookback in (("trend", 50), ("mean_reversion", 50), ("swing_breakout", 100)):
        full = build_feature_pack(frame, lookback, 250)
        again = build_feature_pack(frame, lookback, 250)
        left = [signal_from_arrays(name, index, full) for index in range(len(frame))]
        right = [signal_from_arrays(name, index, again) for index in range(len(frame))]
        assert left == right
        assert left[0][0] is None
        partial = build_feature_pack(frame.iloc[:121], lookback, 250)
        assert signal_from_arrays(name, 120, full) == signal_from_arrays(name, 120, partial)


def test_ranking_rejects_a_smaller_loss() -> None:
    smaller_loss = {"trades": 400, "pnl": -1.0, "profit_factor": 0.99, "max_drawdown_fraction": 0.10}
    large_loss = {"trades": 400, "pnl": -100.0, "profit_factor": 0.20, "max_drawdown_fraction": 0.80}
    assert RANK.assess(smaller_loss, smaller_loss, smaller_loss)["merits_validation"] is False
    assert RANK.assess(large_loss, large_loss, large_loss)["merits_validation"] is False
    passing = {"trades": 120, "pnl": 25.0, "profit_factor": 1.4, "max_drawdown_fraction": 0.10}
    slipped = {"trades": 120, "pnl": 5.0, "profit_factor": 1.1, "max_drawdown_fraction": 0.12}
    assert RANK.assess(passing, passing, slipped) == {"merits_validation": True, "rejections": []}
    ordered = RANK.order_passes(
        [
            {"strategy": "b", "merits_validation": True, "out_of_sample_profit_factor": 1.2, "out_of_sample_drawdown": 0.2},
            {"strategy": "a", "merits_validation": True, "out_of_sample_profit_factor": 1.2, "out_of_sample_drawdown": 0.1},
            {"strategy": "c", "merits_validation": False, "out_of_sample_profit_factor": 9.0, "out_of_sample_drawdown": 0.0},
        ]
    )
    assert ordered == ["a", "b"]


def test_each_candidate_direction_is_risk_gated() -> None:
    for name in ("trend", "mean_reversion", "swing_trend", "swing_mean_reversion", "swing_breakout"):
        if name.startswith("swing"):
            _seed(f"{name}-short")
            short = _run(name, candle_count=50)
            assert _blocked(short, "insufficient_lookback"), (name, short["blocked_by"])
        _clear()
        _seed(f"{name}-eligible")
        first = _run(name)
        assert first["blocked_by"] == "", name
        assert first["broker_requests"] == 1
        assert first["production_eligible"] is False
        second = _run(name, broker=first["broker"])
        assert second["blocked_by"] == "position_already_open"
        assert second["broker_requests"] == 1
        _clear()
        cases = []
        _seed(f"{name}-stop")
        cases.append((_run(name, stop_distance=float("nan")), "sizing_input_invalid"))
        _seed(f"{name}-nav")
        cases.append((_run(name, broker_snapshot=_snap(NAV=None)), "broker_value_nonfinite"))
        _seed(f"{name}-loss", realised=-200.0)
        cases.append((_run(name), "daily_realised_loss_limit"))
        _seed(f"{name}-drawdown", peak=11000.0)
        cases.append((_run(name, broker_snapshot=_snap(NAV=10450.0, balance=10450.0)), "max_drawdown_limit"))
        _seed(f"{name}-exposure")
        os.environ["RISK_MAX_TOTAL_EXPOSURE_PCT"] = "0.5"
        cases.append((_run(name, broker_snapshot=_snap(positions=[{"symbol": "EUR_USD", "units": 100000, "price": 1.1}])), "total_exposure_limit"))
        os.environ["RISK_MAX_TOTAL_EXPOSURE_PCT"] = "1000"
        _clear()
        _seed(f"{name}-reservation")
        note_blocking_reservation("EUR_USD", f"r31-{name}")
        cases.append((_run(name), "active_reservation"))
        _clear()
        _seed(f"{name}-unresolved")
        restore_unresolved_intent("EUR_USD", f"r31-{name}-open")
        cases.append((_run(name), "unresolved_intent"))
        _clear()
        _seed(f"{name}-pages")
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
        cases.append((_run(name, broker_snapshot=None, oanda_summary=summary, oanda_transactions={"pages": ["not-fetched"]}), "transaction_pages_incomplete"))
        for result, reason in cases:
            assert _blocked(result, reason), (name, reason, result["blocked_by"])
    assert all(strategies[name].active is False and strategies[name].authorised_for_live is False for name in NAMES)

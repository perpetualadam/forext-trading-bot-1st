"""Offline R.29 scalp signal and risk-gate checks. No broker, database, or live loop."""

from __future__ import annotations

import importlib.util
import json
import math
import os
import socket
import subprocess
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd


class _BlockedSocket(socket.socket):
    def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("R29_NETWORK_BLOCKED")


def _blocked_name(*_args, **_kwargs):  # noqa: ANN002, ANN003
    raise RuntimeError("R29_DNS_BLOCKED")


socket.socket = _BlockedSocket  # type: ignore[misc]
socket.getaddrinfo = _blocked_name  # type: ignore[assignment]
socket.gethostbyname = _blocked_name  # type: ignore[assignment]
socket.create_connection = _blocked_name  # type: ignore[assignment]
_dotenv = types.ModuleType("dotenv")
_dotenv.load_dotenv = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
sys.modules["dotenv"] = _dotenv

ROOT = Path(__file__).resolve().parents[1]
R29 = ROOT / "data" / "research" / "adaptive_ensemble" / "r29"
R29.mkdir(parents=True, exist_ok=True)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R29 / "synthetic_live_safety_state.json")
sys.path.insert(0, str(ROOT))

from forex_bot.bot_loop import IterationDependencies, evaluate_one_instrument_iteration  # noqa: E402
from forex_bot.database import (  # noqa: E402
    force_order_recovery_fail_closed,
    note_blocking_reservation,
    note_unconfirmed_exposure,
    reset_order_intent_gate_for_tests,
    restore_unresolved_intent,
)
from forex_bot.orders import reset_orders_for_tests  # noqa: E402
from forex_bot.positions import close_position, positions  # noqa: E402
from forex_bot.shadow.reasons import ShadowReason  # noqa: E402
from forex_bot.shadow.signals import (  # noqa: E402
    build_feature_pack,
    prepare_frame,
    signal_from_arrays,
    signal_from_indicators,
)
from forex_bot.strategy_meta import strategies  # noqa: E402

OPEN = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
DAY = "2026-01-07"
ACCOUNT = "synthetic-r29"
LOOKBACK = 50


def _broker():
    spec = importlib.util.spec_from_file_location("r12_fakes", ROOT / "tests" / "r12_fakes.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module.FakeBroker("filled")


def _seed(name: str, *, peak: float = 10000.0, baseline: float = 10000.0, realised: float = 0.0) -> Path:
    path = R29 / "states" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "schema_version": 1,
        "peak_equity": peak,
        "day_baselines": {DAY: baseline},
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
    path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
    os.environ["RISK_STATE_PATH"] = str(path)
    os.environ["RISK_ACCOUNT_ID"] = ACCOUNT
    os.environ["RISK_ACCOUNT_CURRENCY"] = "USD"
    return path


def _limits(exposure: str = "1000") -> None:
    os.environ["RISK_MAX_DAILY_LOSS_PCT"] = "0.02"
    os.environ["RISK_MAX_DRAWDOWN_PCT"] = "0.05"
    os.environ["RISK_MAX_TOTAL_EXPOSURE_PCT"] = exposure


def _bars(n: int = 80, step: float = 0.0002) -> pd.DataFrame:
    rows = []
    for index in range(n):
        close = 1.10 + index * step
        rows.append(
            {
                "time": f"2026-01-07T10:{index % 60:02d}:00+00:00",
                "open": close - 0.00005,
                "high": close + 0.0001,
                "low": close - 0.0001,
                "close": close,
            }
        )
    return pd.DataFrame(rows)


def _prepared(frame: pd.DataFrame | None = None) -> pd.DataFrame:
    ready, status = prepare_frame(frame if frame is not None else _bars(), LOOKBACK)
    assert status == "ok" and ready is not None
    return ready


def _signal(frame: pd.DataFrame | None = None) -> tuple[str | None, str]:
    return signal_from_indicators("scalp", _prepared(frame))


def _snap(**extra: object) -> dict:
    as_of = extra.pop("as_of", OPEN)
    body = {
        "provenance": extra.pop("provenance", "injected_synthetic"),
        "id": extra.pop("id", ACCOUNT),
        "currency": extra.pop("currency", "USD"),
        "snapshot_id": extra.pop("snapshot_id", "r29-snap"),
        "as_of": as_of,
        "NAV": extra.pop("NAV", 10000.0),
        "balance": extra.pop("balance", 10000.0),
        "unrealised": extra.pop("unrealised", 0.0),
        "positions": extra.pop("positions", []),
        "orders": extra.pop("orders", []),
    }
    body.update(extra)
    return body


def _run(**overrides: object) -> dict:
    broker = overrides.pop("broker", None) or _broker()
    direction = overrides.pop("direction", "BUY")
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
        "stop_distance": 0.001,
        "stop_loss": 1.099,
        "take_profit": 1.102,
        "broker": broker,
        "strategy_name": "scalp",
        "strategy_known": True,
        "strategy_active": True,
        "strategy_authorised": True,
        "safety_initialised": True,
        "vote": {"allow": True, "direction": direction, "confidence": 0.8},
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
        and "reservation" not in result["phases"]
    )


def _clear() -> None:
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    for symbol in list(positions):
        close_position(symbol)


def setup_function() -> None:
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    _limits()
    _clear()
    for strategy in strategies.values():
        assert strategy.active is False
        assert strategy.authorised_for_live is False


def test_scalp_signal_is_deterministic_and_directional() -> None:
    frame = _bars()
    first = _signal(frame)
    second = _signal(frame.copy())
    assert first == second == ("BUY", "scalp_momentum_up")
    down = _signal(_bars(step=-0.0002))
    assert down == ("SELL", "scalp_momentum_down")
    flat = _bars(step=0.0)
    assert _signal(flat) == (None, ShadowReason.NO_SIGNAL)


def test_warmup_missing_and_malformed_inputs_do_not_signal() -> None:
    short = _bars(8)
    ready, status = prepare_frame(short, LOOKBACK)
    assert status == "ok" and ready is not None
    assert signal_from_indicators("scalp", ready.iloc[:1]) == (None, ShadowReason.INSUFFICIENT_DATA)
    assert signal_from_indicators("scalp", pd.DataFrame()) == (None, ShadowReason.INSUFFICIENT_DATA)
    broken = _prepared().drop(columns=["close"])
    assert signal_from_indicators("scalp", broken) == (None, ShadowReason.INSUFFICIENT_DATA)
    poisoned = _prepared()
    poisoned.loc[poisoned.index[-1], "close"] = math.inf
    assert signal_from_indicators("scalp", poisoned) == (None, ShadowReason.INSUFFICIENT_DATA)
    poisoned.loc[poisoned.index[-1], "close"] = math.nan
    assert signal_from_indicators("scalp", poisoned) == (None, ShadowReason.INSUFFICIENT_DATA)
    assert signal_from_indicators("not_a_strategy", _prepared()) == (None, ShadowReason.NO_SIGNAL)


def test_signal_does_not_read_future_bars() -> None:
    frame = _bars(90)
    full = build_feature_pack(frame, LOOKBACK, 250)
    for index in (50, 70, 89):
        prefix = frame.iloc[: index + 1].copy()
        partial = build_feature_pack(prefix, LOOKBACK, 250)
        assert signal_from_arrays("scalp", index, full) == signal_from_arrays("scalp", index, partial)


def test_duplicate_and_gapped_bars_emit_one_decision() -> None:
    frame = _prepared()
    assert signal_from_indicators("scalp", frame) == signal_from_indicators("scalp", frame)
    gapped = frame.drop(frame.index[40]).reset_index(drop=True)
    decision = signal_from_indicators("scalp", gapped)
    assert decision[0] in {"BUY", "SELL", None}
    assert len(gapped) == len(frame) - 1
    duplicated = pd.concat([frame, frame.iloc[[-1]]], ignore_index=True)
    assert signal_from_indicators("scalp", duplicated) == signal_from_indicators("scalp", frame)


def test_inactive_strategy_is_not_changed_by_a_signal() -> None:
    before = {name: (item.active, item.authorised_for_live) for name, item in strategies.items()}
    _signal()
    after = {name: (item.active, item.authorised_for_live) for name, item in strategies.items()}
    assert before == after
    assert all(active is False and authorised is False for active, authorised in after.values())


def test_risk_gates_block_without_reservation_or_dispatch() -> None:
    direction, _reason = _signal()
    assert direction == "BUY"
    cases = []
    _seed("loss", realised=-200.0)
    cases.append((_run(direction=direction), "daily_realised_loss_limit"))
    _seed("drawdown", peak=11000.0)
    cases.append((_run(direction=direction, broker_snapshot=_snap(NAV=10450.0, balance=10450.0)), "max_drawdown_limit"))
    _seed("exposure")
    _limits("0.5")
    cases.append(
        (
            _run(
                direction=direction,
                broker_snapshot=_snap(positions=[{"symbol": "EUR_USD", "units": 100000, "price": 1.1}]),
            ),
            "total_exposure_limit",
        )
    )
    _limits()
    _seed("stale")
    cases.append((_run(direction=direction, broker_snapshot=_snap(as_of=OPEN - timedelta(seconds=301))), "account_snapshot_stale"))
    _seed("missing")
    cases.append((_run(direction=direction, broker_snapshot=None, account_present=False, account_payload=None), "account_missing"))
    _seed("nav")
    cases.append(
        (
            _run(
                direction=direction,
                broker_snapshot=None,
                oanda_summary={"account": {"id": ACCOUNT, "currency": "USD", "balance": "10000", "unrealizedPL": "0"}},
            ),
            "broker_equity_missing",
        )
    )
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
    cases.append(
        (
            _run(direction=direction, broker_snapshot=None, oanda_summary=summary, oanda_transactions={"pages": ["not-fetched"]}),
            "transaction_pages_incomplete",
        )
    )
    _seed("price")
    cases.append((_run(direction=direction, bid=0.0), "quote_bid_not_positive"))
    _seed("size")
    cases.append((_run(direction=direction, stop_distance=float("nan")), "sizing_input_invalid"))
    _seed("recovery")
    force_order_recovery_fail_closed()
    cases.append((_run(direction=direction), "recovery_unreadable"))
    _clear()
    _seed("filled")
    note_unconfirmed_exposure("EUR_USD", "r29-filled")
    cases.append((_run(direction=direction), "exposure_unconfirmed"))
    _clear()
    _seed("unresolved")
    restore_unresolved_intent("EUR_USD", "r29-unresolved")
    cases.append((_run(direction=direction), "unresolved_intent"))
    _clear()
    _seed("reservation")
    note_blocking_reservation("EUR_USD", "r29-pending")
    cases.append((_run(direction=direction), "active_reservation"))
    for result, reason in cases:
        assert _blocked(result, reason), (reason, result["blocked_by"], result["phases"])


def test_eligible_signal_reaches_inert_dispatch_once() -> None:
    direction, reason = _signal()
    assert (direction, reason) == ("BUY", "scalp_momentum_up")
    _seed("eligible")
    first = _run(direction=direction)
    assert first["blocked_by"] == ""
    assert first["broker_requests"] == 1
    assert first["production_eligible"] is False
    assert first["details"].get("reservation_attempted") is True
    second = _run(direction=direction, broker=first["broker"])
    assert second["blocked_by"] == "position_already_open"
    assert second["broker_requests"] == 1
    assert second["production_eligible"] is False
    assert all(item.active is False for item in strategies.values())


def test_signal_matches_across_processes() -> None:
    frame = _bars()
    payload = R29 / "states" / "signal_frame.json"
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_text(frame.to_json(orient="records"), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, "-B", str(ROOT / "tests" / "r29_signal_child.py"), str(payload)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    child = json.loads(completed.stdout)
    parent = _signal(frame)
    assert child["direction"] == parent[0]
    assert child["reason"] == parent[1]
    assert child["active"] is False

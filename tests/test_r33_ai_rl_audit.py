"""Offline checks for the R.33 audit. Synthetic votes are not model performance."""

from __future__ import annotations

import importlib.util
import json
import os
import socket
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path


class _BlockedSocket(socket.socket):
    def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("R33_NETWORK_BLOCKED")


def _blocked_name(*_args, **_kwargs):  # noqa: ANN002, ANN003
    raise RuntimeError("R33_DNS_BLOCKED")


socket.socket = _BlockedSocket  # type: ignore[misc]
socket.getaddrinfo = _blocked_name  # type: ignore[assignment]
socket.gethostbyname = _blocked_name  # type: ignore[assignment]
socket.create_connection = _blocked_name  # type: ignore[assignment]
_dotenv = types.ModuleType("dotenv")
_dotenv.load_dotenv = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
sys.modules["dotenv"] = _dotenv
os.environ["ENSEMBLE_MODE"] = "quant"

ROOT = Path(__file__).resolve().parents[1]
R33 = ROOT / "data" / "research" / "adaptive_ensemble" / "r33"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R33 / "synthetic_live_safety_state.json")
sys.path.insert(0, str(ROOT))

from forex_bot.ai_ensemble import AIEnsemble, _quant_stub_vote  # noqa: E402
from forex_bot.bot_loop import (  # noqa: E402
    IterationDependencies,
    _drive_completed,
    evaluate_one_instrument_iteration,
)
from forex_bot.database import reset_order_intent_gate_for_tests  # noqa: E402
from forex_bot.indicators import compute_indicators  # noqa: E402
from forex_bot.orders import reset_orders_for_tests  # noqa: E402
from forex_bot.positions import close_position, positions  # noqa: E402
from forex_bot.rl_agent import RLAgent  # noqa: E402
from forex_bot.strategy_meta import strategies  # noqa: E402

import pandas as pd  # noqa: E402

NAMES = ("scalp", "trend", "mean_reversion", "swing_trend", "swing_mean_reversion", "swing_breakout")
OPEN = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
DAY = "2026-01-07"
ACCOUNT = "synthetic-r33"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


score = _load(R33 / "scoring.py", "r33_scoring_test")


class _FixedAgent:
    def __init__(self, action: object) -> None:
        self.action = action

    def decide(self, _state: str) -> object:
        return self.action


def _broker():
    return _load(ROOT / "tests" / "r12_fakes.py", "r12_fakes_r33").FakeBroker("filled")


def _seed() -> None:
    path = R33 / "states" / "safety.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "peak_equity": 10000.0,
                "day_baselines": {DAY: 10000.0},
                "realised_by_day": {DAY: 0.0},
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
        "snapshot_id": "r33-snap",
        "as_of": OPEN,
        "NAV": 10000.0,
        "balance": 10000.0,
        "unrealised": 0.0,
        "positions": [],
        "orders": [],
    }
    body.update(extra)
    return body


def _candles(count: int = 50) -> list[dict[str, object]]:
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


def _clear() -> None:
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    for symbol in list(positions):
        close_position(symbol)


def _run(**overrides: object) -> dict:
    _clear()
    _seed()
    broker = overrides.pop("broker", None) or _broker()
    values: dict[str, object] = {
        "candles": _candles(),
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
        "strategy_name": "scalp",
        "strategy_known": True,
        "strategy_active": True,
        "strategy_authorised": True,
        "safety_initialised": True,
        "vote": {"allow": True, "direction": "BUY", "confidence": 0.8},
        "invoke_rl": True,
        "rl_agent": _FixedAgent("BUY"),
        "account_payload": {"id": ACCOUNT},
        "expected_account_id": ACCOUNT,
        "expected_account_currency": "USD",
        "broker_snapshot": _snap(),
    }
    values.update(overrides)
    result = evaluate_one_instrument_iteration("EUR_USD", IterationDependencies(**values))  # type: ignore[arg-type]
    result["broker_requests"] = broker.request_count
    return result


def _blocked(result: dict, reason: str) -> bool:
    return (
        result["blocked_by"] == reason
        and result["broker_requests"] == 0
        and result["details"].get("reservation_attempted") is False
        and result["production_eligible"] is False
    )


def test_stub_cannot_approve_and_features_stay_causal() -> None:
    frame = pd.DataFrame(
        {
            "open": [1.1 + index * 0.0001 for index in range(40)],
            "high": [1.1003 + index * 0.0001 for index in range(40)],
            "low": [1.0997 + index * 0.0001 for index in range(40)],
            "close": [1.1 + index * 0.0001 for index in range(40)],
        }
    )
    full = compute_indicators(frame)
    prefix = compute_indicators(frame.iloc[:30])
    assert float(full["ma_fast"].iloc[29]) == float(prefix["ma_fast"].iloc[-1])
    left = _quant_stub_vote({"price": 1.1, "ma_fast": 1.2, "ma_slow": 1.0, "returns": 0.001, "atr": 0.001})
    right = _quant_stub_vote({"price": 1.1, "ma_fast": 1.0, "ma_slow": 1.2, "returns": -0.001, "atr": 0.001})
    assert left == right
    assert left["allow"] is False
    assert left["direction"] is None
    assert left["reason"] == "quant_stub_removed"


def test_empty_ensemble_does_not_become_an_entry() -> None:
    vote = _drive_completed(AIEnsemble([]).vote({}, "EUR_USD"))
    assert vote["allow"] is False
    assert vote["direction"] is None
    result = _run(vote=vote, invoke_rl=False, rl_agent=None)
    assert _blocked(result, "ai_vote_rejected")


def test_invalid_votes_and_rl_actions_stay_closed() -> None:
    assert _blocked(_run(vote={"allow": True, "direction": "HOLD", "confidence": 0.9}), "invalid_entry_direction")
    assert _blocked(_run(vote={"allow": True, "direction": "BUY", "confidence": float("nan")}), "ai_vote_nonfinite")
    assert _blocked(_run(rl_agent=_FixedAgent("SKIP")), "rl_veto")
    assert _blocked(_run(rl_agent=_FixedAgent("SELL")), "rl_direction_mismatch")
    assert _blocked(_run(rl_agent=_FixedAgent("UNAVAILABLE")), "rl_state_unavailable")
    assert _blocked(_run(stop_distance=float("nan")), "sizing_input_invalid")
    assert _blocked(_run(broker_snapshot=_snap(NAV=None)), "broker_value_nonfinite")
    fresh = RLAgent()
    assert fresh.persisted_ok is False
    assert fresh.decide("unseen") == "UNAVAILABLE"
    assert all(strategies[name].active is False and strategies[name].authorised_for_live is False for name in NAMES)


def test_decision_labels_follow_the_protocol() -> None:
    quarters = [{"count": 40, "mean": 0.01} for _ in range(4)]
    interval = (0.001, 0.02)
    assert score.decide_stub(-0.01, 0.02, interval, 0.0, 0.0, 0.0001, quarters)["classification"] == "EVALUABLE_NO_CREDIBLE_EDGE"
    assert score.decide_stub(0.01, -0.01, interval, 0.0, 0.0, 0.0001, quarters)["classification"] == "INCONCLUSIVE"
    assert score.decide_stub(0.01, 0.02, (-0.001, 0.02), 0.0, 0.0, 0.0001, quarters)["classification"] == "INCONCLUSIVE"
    passed = score.decide_stub(0.01, 0.02, interval, 0.0, 0.0, 0.0001, quarters)
    assert passed == {"classification": "INCONCLUSIVE", "rule": "exposed_period"}
    assert score.decide_stub(0.00005, 0.00004, (0.00001, 0.00008), 0.0, 0.0, 0.0001, quarters)["classification"] == "EVALUABLE_NO_CREDIBLE_EDGE"

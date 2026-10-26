"""Offline checks for the R.34 voting, RL, and volatility hardening."""

from __future__ import annotations

import inspect
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
        raise RuntimeError("R34_NETWORK_BLOCKED")


def _blocked_name(*_args, **_kwargs):  # noqa: ANN002, ANN003
    raise RuntimeError("R34_DNS_BLOCKED")


socket.socket = _BlockedSocket  # type: ignore[misc]
socket.getaddrinfo = _blocked_name  # type: ignore[assignment]
socket.gethostbyname = _blocked_name  # type: ignore[assignment]
socket.create_connection = _blocked_name  # type: ignore[assignment]
_dotenv = types.ModuleType("dotenv")
_dotenv.load_dotenv = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
sys.modules["dotenv"] = _dotenv
os.environ["ENSEMBLE_MODE"] = "hybrid"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
for _key in (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "MISTRAL_API_KEY",
    "XAI_API_KEY",
    "GROK_API_KEY",
    "GROQ_API_KEY",
    "VENICE_API_KEY",
    "QROK_API_KEY",
    "OPENAI_BASE_URL",
):
    os.environ.pop(_key, None)

ROOT = Path(__file__).resolve().parents[1]
R34 = ROOT / "data" / "research" / "adaptive_ensemble" / "r34"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R34 / "synthetic_live_safety_state.json")
sys.path.insert(0, str(ROOT))

from forex_bot.ai_ensemble import (  # noqa: E402
    AIEnsemble,
    LocalLLM,
    _build_default_ensemble,
    _quant_stub_vote,
)
from forex_bot.bot_loop import (  # noqa: E402
    IterationDependencies,
    _drive_completed,
    evaluate_one_instrument_iteration,
)
from forex_bot.database import (  # noqa: E402
    note_blocking_reservation,
    reset_order_intent_gate_for_tests,
    restore_unresolved_intent,
)
from forex_bot.execution_risk import load_offline_harness  # noqa: E402
from forex_bot.orders import reset_orders_for_tests  # noqa: E402
from forex_bot.positions import close_position, positions  # noqa: E402
from forex_bot.research.decision_journal import RESEARCH_ONLY as JOURNAL_ONLY  # noqa: E402
from forex_bot.research.decision_journal import JournalRejected, validate_journal_record  # noqa: E402
from forex_bot.research.ml_prediction import RESEARCH_ONLY as PREDICTION_ONLY  # noqa: E402
from forex_bot.research.ml_prediction import PredictionRejected, validate_prediction  # noqa: E402
from forex_bot.rl_agent import RLAgent  # noqa: E402
from forex_bot.session_rules import volatility_ok  # noqa: E402
from forex_bot.strategy_meta import strategies  # noqa: E402

NAMES = ("scalp", "trend", "mean_reversion", "swing_trend", "swing_mean_reversion", "swing_breakout")
OPEN = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
DAY = "2026-01-07"
ACCOUNT = "synthetic-r34"
HASH = "a" * 64


class _FixedAgent:
    def __init__(self, action: object) -> None:
        self.action = action

    def decide(self, _state: str) -> object:
        return self.action


class _Voter:
    def __init__(self, response: dict) -> None:
        self.response = response

    async def predict(self, _payload: dict) -> dict:
        return dict(self.response)


def _broker():
    import importlib.util

    spec = importlib.util.spec_from_file_location("r12_fakes_r34", ROOT / "tests" / "r12_fakes.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module.FakeBroker("filled")


def _seed(name: str, *, peak: float, baseline: float, realised: float) -> None:
    path = R34 / "states" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
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
        ),
        encoding="utf-8",
    )
    os.environ["RISK_STATE_PATH"] = str(path)
    os.environ["RISK_ACCOUNT_ID"] = ACCOUNT
    os.environ["RISK_ACCOUNT_CURRENCY"] = "USD"
    os.environ["RISK_MAX_DAILY_LOSS_PCT"] = "0.02"
    os.environ["RISK_MAX_DRAWDOWN_PCT"] = "0.05"
    os.environ["RISK_MAX_TOTAL_EXPOSURE_PCT"] = "1000"


def _clear() -> None:
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    for symbol in list(positions):
        close_position(symbol)


def _candles(count: int = 50) -> list[dict[str, object]]:
    end = datetime(2026, 1, 7, 11, 58, tzinfo=timezone.utc)
    return [
        {
            "open": 1.1,
            "high": 1.1002,
            "low": 1.0998,
            "close": 1.1,
            "time": (end - timedelta(minutes=5 * (count - 1 - index))).isoformat(),
        }
        for index in range(count)
    ]


def _snap(**extra: object) -> dict:
    body = {
        "provenance": "injected_synthetic",
        "id": ACCOUNT,
        "currency": "USD",
        "snapshot_id": "r34-snap",
        "as_of": OPEN,
        "NAV": 10000.0,
        "balance": 10000.0,
        "unrealised": 0.0,
        "positions": [],
        "orders": [],
    }
    body.update(extra)
    return body


def _run(symbol: str = "EUR_USD", **overrides: object) -> dict:
    _clear()
    setup = overrides.pop("setup", None)
    if setup is not None:
        setup()
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
    result = evaluate_one_instrument_iteration(symbol, IterationDependencies(**values))  # type: ignore[arg-type]
    result["broker_requests"] = broker.request_count
    return result


def _blocked(result: dict, reason: str) -> bool:
    return (
        result["blocked_by"] == reason
        and result["broker_requests"] == 0
        and result["details"].get("reservation_attempted") is False
        and result["production_eligible"] is False
    )


def _prediction(**extra: object) -> dict:
    body = {
        "model_id": "research-demo",
        "model_version": "0",
        "artifact_sha256": HASH,
        "feature_schema_version": "schema-1",
        "instrument": "EUR_USD",
        "timeframe": "M5",
        "predicted_at": OPEN.isoformat(),
        "direction": "BUY",
        "probabilities": {"BUY": 0.7, "SELL": 0.3},
        "confidence": 0.7,
        "status": "approved",
        "validation_status": "validated_offline",
        "reason": "",
    }
    body.update(extra)
    return body


def _journal(**extra: object) -> dict:
    body = {
        "decision_at": OPEN,
        "instrument": "EUR_USD",
        "timeframe": "M5",
        "feature_schema_version": "schema-1",
        "model_id": "research-demo",
        "model_version": "0",
        "artifact_sha256": HASH,
        "prediction_direction": "BUY",
        "probabilities": {"BUY": 0.7, "SELL": 0.3},
        "decision": "accepted",
        "spread": 0.00016,
        "market_condition": "synthetic",
        "risk_rejection_reason": "",
        "outcome_return": 0.0002,
        "prediction_error": 0.0,
        "outcome_evaluable": True,
        "adverse_outcome": False,
        "data_provenance": "synthetic",
        "model_provenance": "not_trained",
    }
    body.update(extra)
    return body


def test_quant_stub_is_absent_from_operational_registration() -> None:
    source = inspect.getsource(_build_default_ensemble)
    assert "LocalLLM(" not in source
    retired = _quant_stub_vote({"ma_fast": 2.0, "ma_slow": 1.0, "returns": 0.01, "atr": 0.01})
    assert retired["allow"] is False and retired["direction"] is None
    local = _drive_completed(LocalLLM().predict({}))
    assert local["direction"] is None and local["reason"] == "quant_stub_removed"
    os.environ["ENSEMBLE_MODE"] = "quant"
    os.environ["AI_DISABLE_STUB"] = "false"
    quant = _build_default_ensemble()
    quant_vote = _drive_completed(quant.vote({}, "EUR_USD"))
    assert quant.local_llms == [] and quant.external_llms == []
    assert quant_vote["reason"] == "unsupported_ensemble_mode"
    assert quant_vote["direction"] is None
    os.environ["ENSEMBLE_MODE"] = "hybrid"
    hybrid = _build_default_ensemble()
    hybrid_vote = _drive_completed(hybrid.vote({}, "EUR_USD"))
    assert hybrid.local_llms == []
    assert all(type(voter).__name__ != "LocalLLM" for voter in hybrid.external_llms)
    assert hybrid_vote["reason"] == "no_voters"
    assert hybrid_vote["direction"] is None
    empty = _drive_completed(AIEnsemble([]).vote({}, "EUR_USD"))
    assert empty["allow"] is False and empty["direction"] is None


def test_invalid_votes_and_rl_state_fail_closed() -> None:
    load_offline_harness(R34)
    _seed("vote", peak=10000.0, baseline=10000.0, realised=0.0)
    assert _blocked(_run(vote=None, empty_voters=True, invoke_rl=False, rl_agent=None), "ai_vote_rejected")
    assert _blocked(_run(vote={"allow": True, "direction": "HOLD", "confidence": 0.9}), "invalid_entry_direction")
    assert _blocked(_run(vote={"allow": True, "direction": "BUY", "confidence": float("nan")}), "ai_vote_nonfinite")
    tied = _drive_completed(
        AIEnsemble(
            [
                _Voter({"allow": True, "direction": "BUY", "confidence": 0.5}),
                _Voter({"allow": True, "direction": "SELL", "confidence": 0.5}),
            ]
        ).vote({}, "EUR_USD")
    )
    assert tied["allow"] is False and tied["direction"] is None
    assert _blocked(_run(vote=tied), "ai_vote_rejected")
    fresh = RLAgent()
    assert fresh.decide("missing") == "UNAVAILABLE"
    fresh.persisted_ok = True
    assert fresh.decide("empty") == "UNAVAILABLE"
    assert _blocked(_run(rl_agent=_FixedAgent("UNAVAILABLE")), "rl_state_unavailable")
    assert _blocked(_run(rl_agent=_FixedAgent("SELL")), "rl_direction_mismatch")
    assert _blocked(_run(rl_agent=fresh), "rl_state_unavailable")
    assert all(strategies[name].active is False and strategies[name].authorised_for_live is False for name in NAMES)


def test_volatility_gate_is_prefix_invariant() -> None:
    calm = pd.DataFrame({"atr": [0.001] * 40})
    extended = pd.DataFrame({"atr": [0.001] * 40 + [5.0] * 30})
    assert volatility_ok(calm, index=39) is True
    assert volatility_ok(extended, index=39) == volatility_ok(calm)
    assert volatility_ok(extended.iloc[:40]) == volatility_ok(extended, index=39)
    assert volatility_ok(calm.iloc[:10]) is False
    assert volatility_ok(pd.DataFrame({"atr": [0.001] * 29 + [float("nan")]})) is False
    spiked = pd.DataFrame({"atr": [0.001] * 29 + [1.0]})
    assert volatility_ok(spiked) is False
    short = _run(candles=_candles(3), invoke_rl=False, rl_agent=None)
    assert _blocked(short, "volatility_unsafe")


def test_prediction_contract_and_journal_reject_bad_rows() -> None:
    assert PREDICTION_ONLY is True and JOURNAL_ONLY is True
    accepted = validate_prediction(_prediction(), evaluated_at=OPEN + timedelta(minutes=5))
    assert accepted.direction == "BUY" and accepted.status == "approved"
    stale = _prediction(predicted_at=(OPEN - timedelta(hours=3)).isoformat())
    try:
        validate_prediction(stale, evaluated_at=OPEN)
        raise AssertionError("stale prediction was accepted")
    except PredictionRejected as exc:
        assert str(exc) == "stale_or_future_prediction"
    try:
        validate_prediction(_prediction(confidence=float("nan")), evaluated_at=OPEN)
        raise AssertionError("non-finite confidence was accepted")
    except PredictionRejected as exc:
        assert str(exc) == "nonfinite_confidence"
    try:
        validate_prediction(_prediction(validation_status="unvalidated"), evaluated_at=OPEN)
        raise AssertionError("unvalidated approval was accepted")
    except PredictionRejected as exc:
        assert str(exc) == "unvalidated_approval"
    held = validate_prediction(
        _prediction(status="abstain", direction=None, confidence=None, probabilities=None, validation_status="unvalidated"),
        evaluated_at=OPEN,
    )
    assert held.direction is None
    sound = validate_journal_record(_journal(prediction_error=0.0, adverse_outcome=True, outcome_return=-0.0004))
    assert sound.prediction_error == 0.0 and sound.adverse_outcome is True
    poor = validate_journal_record(_journal(prediction_error=0.0004, adverse_outcome=True, outcome_return=-0.0004))
    assert poor.prediction_error == 0.0004
    unevaluable = validate_journal_record(
        _journal(
            decision="abstained",
            prediction_direction=None,
            outcome_evaluable=False,
            outcome_return=None,
            prediction_error=None,
            adverse_outcome=None,
            risk_rejection_reason="ai_vote_rejected",
        )
    )
    assert unevaluable.outcome_evaluable is False
    try:
        validate_journal_record(_journal(outcome_evaluable=False, prediction_error=0.1))
        raise AssertionError("an unevaluable row kept an error")
    except JournalRejected as exc:
        assert str(exc) == "unevaluable_outcome_has_values"


def test_shared_evaluate_blocks_risk_and_recovery_cases() -> None:
    load_offline_harness(R34)
    _seed("daily", peak=10000.0, baseline=10000.0, realised=-200.0)
    assert _blocked(_run(invoke_rl=False, rl_agent=None), "daily_realised_loss_limit")
    _seed("drawdown", peak=10000.0, baseline=1_000_000_000.0, realised=0.0)
    assert _blocked(
        _run(
            balance=9500.0,
            broker_snapshot=_snap(NAV=9500.0, balance=9500.0),
            invoke_rl=False,
            rl_agent=None,
        ),
        "max_drawdown_limit",
    )
    _seed("exposure", peak=10000.0, baseline=1_000_000_000.0, realised=0.0)
    os.environ["RISK_MAX_TOTAL_EXPOSURE_PCT"] = "1"
    assert _blocked(_run(invoke_rl=False, rl_agent=None), "total_exposure_limit")
    os.environ["RISK_MAX_TOTAL_EXPOSURE_PCT"] = "1000"
    _seed("nav", peak=10000.0, baseline=1_000_000_000.0, realised=0.0)
    assert _blocked(_run(broker_snapshot=_snap(NAV=None), invoke_rl=False, rl_agent=None), "broker_value_nonfinite")
    assert _blocked(_run(stop_distance=float("nan"), invoke_rl=False, rl_agent=None), "sizing_input_invalid")
    _seed("reservation", peak=10000.0, baseline=1_000_000_000.0, realised=0.0)
    pending = _run(
        "AUD_USD",
        price=0.65,
        bid=0.64995,
        ask=0.65005,
        invoke_rl=False,
        rl_agent=None,
        setup=lambda: note_blocking_reservation("AUD_USD", "cid-pending"),
    )
    assert _blocked(pending, "active_reservation")
    _seed("intent", peak=10000.0, baseline=1_000_000_000.0, realised=0.0)
    unresolved = _run(
        "GBP_USD",
        price=1.27,
        bid=1.26995,
        ask=1.27005,
        invoke_rl=False,
        rl_agent=None,
        setup=lambda: restore_unresolved_intent("GBP_USD", "cid-unresolved"),
    )
    assert _blocked(unresolved, "unresolved_intent")
    _seed("pages", peak=10000.0, baseline=1_000_000_000.0, realised=0.0)
    pages = _run(
        invoke_rl=False,
        rl_agent=None,
        oanda_summary={
            "observed_at": OPEN.isoformat(),
            "account": {
                "id": ACCOUNT,
                "currency": "USD",
                "NAV": "10000.0000",
                "balance": "10000.0000",
                "unrealizedPL": "0.0000",
                "positions": [],
                "orders": [],
            },
        },
        oanda_transactions={"pages": ["https://example.invalid/transactions"], "lastTransactionID": "2"},
    )
    assert _blocked(pages, "transaction_pages_incomplete")
    assert all(strategies[name].active is False and strategies[name].authorised_for_live is False for name in NAMES)

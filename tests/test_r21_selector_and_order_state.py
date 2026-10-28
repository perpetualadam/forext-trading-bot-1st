"""Authoritative selector results and ambiguous-order recovery. Offline only."""

from __future__ import annotations

import importlib.util
import inspect
import json
import os
import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R21 = ROOT / "data" / "research" / "adaptive_ensemble" / "r21"
R21.mkdir(parents=True, exist_ok=True)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R21 / "synthetic_live_safety_state.json")
os.environ.pop("HYBRID_EUR_USD", None)
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from forex_bot import database  # noqa: E402
from forex_bot.bot_loop import (  # noqa: E402
    IterationDependencies,
    _authoritative_strategy,
    evaluate,
    production_execution_adapter,
    rl_decision_state,
    run_bot,
    strategy_entry_block_reason,
)
from forex_bot.database import (  # noqa: E402
    confirm_exposure_flat,
    exposure_entry_block_reason,
    reset_order_intent_gate_for_tests,
    select_rows_for_recovery,
)
from forex_bot.decision_repair.selection import select_deterministic  # noqa: E402
from forex_bot.indicators import compute_indicators  # noqa: E402
from forex_bot.orders import OrderStatus, ingest_recovery_snapshot, orders_by_client_id, reset_orders_for_tests  # noqa: E402
from forex_bot.positions import close_position, positions  # noqa: E402
from forex_bot.rl_agent import RLAgent  # noqa: E402
from forex_bot.strategy_meta import select_strategy, strategies  # noqa: E402

_fake_spec = importlib.util.spec_from_file_location("r12_fakes", ROOT / "tests" / "r12_fakes.py")
_fake_mod = importlib.util.module_from_spec(_fake_spec)
assert _fake_spec is not None and _fake_spec.loader is not None
_fake_spec.loader.exec_module(_fake_mod)
FakeBroker = _fake_mod.FakeBroker

OPEN = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
SYMBOL = "EUR_USD"
NAMES = ("scalp", "trend", "mean_reversion", "swing_trend", "swing_mean_reversion", "swing_breakout")


def _bars(n: int = 50) -> list[dict[str, float | str]]:
    price = 1.1
    return [
        {
            "open": price,
            "high": price + 0.0002,
            "low": price - 0.0002,
            "close": price,
            "time": "2026-01-07T11:58:00+00:00" if index == n - 1 else f"2026-01-07T10:{index % 60:02d}:00+00:00",
        }
        for index in range(n)
    ]


def _agent(bars: list[dict[str, float | str]]) -> RLAgent:
    import pandas as pd

    key = rl_decision_state(compute_indicators(pd.DataFrame(bars)))
    agent = RLAgent(epsilon=0.0)
    agent.q[key] = {"BUY": 1.0, "SELL": 0.0, "SKIP": 0.0}
    agent.persisted_ok = True
    return agent


def _deps(broker: object, **extra: object) -> IterationDependencies:
    bars = extra.pop("candles", None) or _bars()
    values: dict[str, object] = {
        "candles": bars,
        "balance": 10000.0,
        "account_present": True,
        "account_context": "isolated_test",
        "simulation": True,
        "now": OPEN,
        "quote_as_of": OPEN,
        "bid": 1.09995,
        "ask": 1.10005,
        "price": 1.1,
        "stop_distance": 0.001,
        "stop_loss": 1.09895,
        "take_profit": 1.10205,
        "broker": broker,
        "strategy_name": "scalp",
        "strategy_known": True,
        "strategy_active": True,
        "strategy_authorised": True,
        "safety_initialised": True,
        "vote": {"allow": True, "direction": "BUY", "confidence": 0.8},
        "invoke_selector": True,
        "invoke_vote": True,
        "invoke_rl": True,
        "rl_agent": _agent(bars),
    }
    values.update(extra)
    if "unrealised" not in extra:
        values["unrealised"] = 0.0
    if "account_as_of" not in extra:
        values["account_as_of"] = values.get("now")
    return IterationDependencies(**values)  # type: ignore[arg-type]


def _drive(coro: object) -> dict:
    try:
        while True:
            coro.send(None)  # type: ignore[attr-defined]
    except StopIteration as stop:
        return dict(stop.value)


def _cycle(broker: object, **extra: object) -> dict:
    return _drive(evaluate(SYMBOL, _deps(broker, **extra)))


def setup_function() -> None:
    from forex_bot.execution_risk import load_offline_harness
    load_offline_harness(R21)
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(R21 / "synthetic_live_safety_state.json")
    os.environ.pop("HYBRID_EUR_USD", None)
    os.environ.pop("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", None)
    os.environ.pop("MAX_POSITION_UNITS", None)
    os.environ.pop("DECISION_REPAIR_ACCOUNT_RISK", None)
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    for symbol in list(positions):
        close_position(symbol)


def _flags() -> dict[str, tuple[bool, bool]]:
    return {name: (strategies[name].active, strategies[name].authorised_for_live) for name in NAMES}


def test_01_valid_selector_controls_strategy() -> None:
    before = _flags()
    broker = FakeBroker("filled")
    result = _cycle(broker, strategy_name="trend", strategy_active_map={"scalp": True})
    order = orders_by_client_id[result["client_order_id"]]
    assert result["details"]["selected_strategy"] == "scalp"
    assert result["details"]["strategy_name"] == "scalp"
    assert result["details"]["supplied_strategy_ignored"] == "trend"
    assert result["details"]["risk_decision"]["strategy"] == "scalp"
    assert broker.request_count == 1
    assert order.status == OrderStatus.FILLED
    assert before == _flags()


def test_02_null_selector_blocks() -> None:
    broker = FakeBroker("filled")
    result = _cycle(broker, strategy_active_map=None)
    assert result["details"]["selector_called"] is True
    assert result["details"]["selected_strategy"] is None
    assert result["blocked_by"] == "NO_STRATEGY_SELECTED"
    assert result["details"].get("strategy_name") is None
    assert result["details"]["supplied_strategy_ignored"] == "scalp"
    assert "reservation" not in result["phases"]
    assert "fake_broker" not in result["phases"]
    assert broker.request_count == 0
    assert result["details"]["vote_wrapper_called"] is False


def test_03_unknown_selector_result_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    def _unknown(_symbol: str, _frame: object) -> tuple[str, int, str]:
        return ("not_a_strategy", 50, "legacy")

    monkeypatch.setattr("forex_bot.bot_loop.select_strategy", _unknown)
    broker = FakeBroker("filled")
    result = _cycle(broker, strategy_active_map=None, strategy_name="scalp")
    assert result["blocked_by"] == "UNKNOWN_STRATEGY"
    assert broker.request_count == 0
    assert "sizing" not in result["phases"]


def test_04_malformed_selector_result_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    def _malformed(_symbol: str, _frame: object) -> tuple[int, int, str]:
        return (7, 50, "legacy")

    monkeypatch.setattr("forex_bot.bot_loop.select_strategy", _malformed)
    name, reason, active = _authoritative_strategy(7, active_map=None)
    broker = FakeBroker("filled")
    result = _cycle(broker, strategy_active_map=None)
    assert name is None and active is False and reason == "selector_result_malformed"
    assert result["blocked_by"] == "selector_result_malformed"
    assert broker.request_count == 0


def test_05_inactive_selector_result_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    import numpy as np

    monkeypatch.setenv("HYBRID_EUR_USD", "1")
    np.random.seed(0)
    broker = FakeBroker("filled")
    result = _cycle(broker, strategy_active_map=None, strategy_name="scalp")
    selected = result["details"]["selected_strategy"]
    assert selected in NAMES
    assert strategies[selected].active is False
    assert result["blocked_by"] == "STRATEGY_INACTIVE"
    assert result["details"]["strategy_name"] == selected
    assert broker.request_count == 0
    assert all(strategies[name].active is False and strategies[name].authorised_for_live is False for name in NAMES)


def test_06_supplied_name_cannot_override_valid_selection() -> None:
    broker = FakeBroker("filled")
    result = _cycle(broker, strategy_name="swing_breakout", strategy_active_map={"trend": True})
    assert result["details"]["selected_strategy"] == "trend"
    assert result["details"]["strategy_name"] == "trend"
    assert result["details"]["supplied_strategy_ignored"] == "swing_breakout"
    assert broker.requests[0]["symbol"] == SYMBOL


def test_07_supplied_name_cannot_replace_null() -> None:
    broker = FakeBroker("filled")
    result = _cycle(broker, strategy_name="scalp", strategy_active=True, strategy_active_map={})
    assert result["details"]["selected_strategy"] is None
    assert result["blocked_by"] == "NO_STRATEGY_SELECTED"
    assert result["details"].get("strategy_name") is None
    assert broker.request_count == 0


def test_08_selector_exception_blocks() -> None:
    broker = FakeBroker("filled")
    result = _cycle(broker, selector_error="boom")
    assert result["blocked_by"] == "strategy_selection_error"
    assert broker.request_count == 0
    assert "reservation" not in result["phases"]


def test_09_selector_unavailable_blocks() -> None:
    broker = FakeBroker("filled")
    result = _cycle(broker, selector_error="unavailable")
    assert result["blocked_by"] == "strategy_selection_unavailable"
    assert broker.request_count == 0


def test_10_selected_strategy_controls_lookback_and_metadata() -> None:
    broker = FakeBroker("filled")
    result = _cycle(broker, strategy_name="swing_trend", strategy_active_map={"scalp": True})
    details = result["details"]
    assert details["selected_strategy"] == "scalp"
    assert details["lookback_required"] == details["lookback"] == 50
    assert details["risk_decision"]["strategy"] == "scalp"
    assert details["risk_decision"]["decision_id"].endswith("|scalp")
    assert len(result["phases"]) > 0
    assert broker.request_count == 1


def test_11_ai_and_rl_cannot_override_selector_rejection() -> None:
    broker = FakeBroker("filled")
    result = _cycle(
        broker,
        strategy_active_map={},
        vote={"allow": True, "direction": "BUY", "confidence": 0.99},
        invoke_vote=True,
        invoke_rl=True,
    )
    assert result["blocked_by"] == "NO_STRATEGY_SELECTED"
    assert result["details"]["vote_wrapper_called"] is False
    assert result["details"]["rl_veto_called"] is False
    assert broker.request_count == 0


def test_12_actual_selector_implementation() -> None:
    import pandas as pd

    frame = compute_indicators(pd.DataFrame(_bars()))
    legacy_name, _lookback, _horizon = select_strategy(SYMBOL, frame)
    chosen = select_deterministic(SYMBOL, frame, active_override={"scalp": True}, persist=False)
    broker = FakeBroker("filled")
    result = _cycle(broker, strategy_name="mean_reversion", strategy_active_map={"scalp": True})
    assert legacy_name is None
    assert chosen.selected == "scalp"
    assert chosen.reason == "rotate_active_eligible"
    assert result["details"]["selected_strategy"] == chosen.selected
    assert result["details"]["strategy_name"] == "scalp"
    assert all(strategies[name].active is False for name in NAMES)
    assert result["production_eligible"] is False


def test_13_filled_two_cycle_hold() -> None:
    first_broker = FakeBroker("filled")
    second_broker = FakeBroker("filled")
    first = _cycle(first_broker, strategy_name="trend", strategy_active_map={"scalp": True})
    second = _cycle(second_broker, now=OPEN + timedelta(minutes=1), strategy_active_map={"scalp": True})
    assert first["outcome"] == "recorded"
    assert first_broker.request_count == 1
    assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"
    assert second["details"]["exposure_read"] == "exposure_unconfirmed"
    assert second["blocked_by"] == "position_already_open"
    assert second["details"]["reservation_attempted"] is False
    assert second_broker.request_count == 0
    assert "reservation" not in second["phases"]


def test_14_ambiguous_order_is_unresolved_with_exposure() -> None:
    broker = FakeBroker("ambiguous")
    result = _cycle(broker, strategy_active_map={"scalp": True})
    order = orders_by_client_id[result["client_order_id"]]
    assert broker.request_count == 1
    assert result["outcome"] == "ambiguous"
    assert order.status == OrderStatus.UNRESOLVED
    assert order.detail == "ambiguous_broker_outcome"
    assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"
    assert SYMBOL in database._process_unresolved
    assert result["exposure_held"] is True


def test_15_ambiguous_second_cycle_blocks_without_retry() -> None:
    first_broker = FakeBroker("ambiguous")
    second_broker = FakeBroker("filled")
    first = _cycle(first_broker, strategy_active_map={"scalp": True})
    second = _cycle(second_broker, now=OPEN + timedelta(minutes=1), strategy_active_map={"scalp": True})
    assert first_broker.request_count == 1
    assert second["blocked_by"] == "exposure_unconfirmed"
    assert second["details"]["reservation_attempted"] is False
    assert second_broker.request_count == 0
    assert orders_by_client_id[first["client_order_id"]].status == OrderStatus.UNRESOLVED
    assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"


def test_16_timeout_retains_exposure() -> None:
    broker = FakeBroker("filled", error=TimeoutError("offline timeout"))
    result = _cycle(broker, strategy_active_map={"scalp": True})
    order = orders_by_client_id[result["client_order_id"]]
    assert broker.request_count == 1
    assert result["outcome"] == "timeout"
    assert order.status == OrderStatus.UNRESOLVED
    assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"
    follow = _cycle(FakeBroker("filled"), now=OPEN + timedelta(minutes=1), strategy_active_map={"scalp": True})
    assert follow["blocked_by"] == "exposure_unconfirmed"
    assert follow["broker_requests"] == 0


def test_17_partial_retains_exposure() -> None:
    broker = FakeBroker("partial", response={"kind": "partial", "units": 1, "price": 1.10005, "broker_order_id": "SIMULATED"})
    result = _cycle(broker, strategy_active_map={"scalp": True})
    order = orders_by_client_id[result["client_order_id"]]
    assert order.status == OrderStatus.PARTIAL
    assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"
    follow = _cycle(FakeBroker("filled"), now=OPEN + timedelta(minutes=1), strategy_active_map={"scalp": True})
    assert follow["details"]["exposure_read"] == "exposure_unconfirmed"
    assert follow["broker_requests"] == 0
    assert "reservation" not in follow["phases"]


def test_18_persistence_failure_blocks() -> None:
    broker = FakeBroker("filled")
    result = _cycle(broker, strategy_active_map={"scalp": True}, persistence_failure="unavailable")
    assert result["blocked_by"] == "reservation_persistence_failed"
    assert broker.request_count == 0
    assert database._pg_conn is None


def test_19_historical_filled_remains_held() -> None:
    rows = [{"client_order_id": "hist-r21", "symbol": SYMBOL, "status": "FILLED", "metadata": {}}]
    kept = select_rows_for_recovery(rows)
    assert kept
    ingest_recovery_snapshot(kept, True)
    broker = FakeBroker("filled")
    result = _cycle(broker, strategy_active_map={"scalp": True})
    assert result["blocked_by"] == "exposure_unconfirmed"
    assert broker.request_count == 0
    assert confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT", verified=True) is False
    assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"


def test_20_caller_flat_marker_cannot_clear_exposure() -> None:
    _cycle(FakeBroker("ambiguous"), strategy_active_map={"scalp": True})
    assert confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False
    assert confirm_exposure_flat(SYMBOL, evidence={"flat": True}) is False
    follow = _cycle(FakeBroker("filled"), now=OPEN + timedelta(minutes=1), strategy_active_map={"scalp": True})
    assert follow["blocked_by"] == "exposure_unconfirmed"
    assert follow["broker_requests"] == 0


def test_21_eligibility_and_adapter_stay_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    async def stub(*_args: object, **_kwargs: object) -> dict:
        calls.append(1)
        return {"unexpected": True}

    import forex_bot.oanda_exec as oanda_exec

    monkeypatch.setattr(oanda_exec, "execute_oanda_market_open", stub)
    result = _cycle(FakeBroker("filled"), strategy_active_map={"scalp": True})
    decision = result["details"]["risk_decision"]
    assert result["production_eligible"] is False
    assert decision["production_eligible"] is False
    synthetic = _drive(
        production_execution_adapter(
            SYMBOL, 10, "BUY", "cid", stop_loss=1, take_profit=2,
            execution_kind="production", entry_quote=None, risk_decision=decision, reservation_id="cid",
        )
    )
    forged = dict(decision)
    forged["production_eligible"] = True
    forged["context"] = "production"
    forged["seal_id"] = "forged-r21"
    forged_result = _drive(
        production_execution_adapter(
            SYMBOL, 10, "BUY", "cid", stop_loss=1, take_profit=2,
            execution_kind="production", entry_quote=None, risk_decision=forged,
        )
    )
    assert synthetic["reason"] == "synthetic_context_rejected"
    assert forged_result["broker_called"] is False
    assert calls == []


def test_22_no_broker_database_network_or_launcher(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    async def stub(*_args: object, **_kwargs: object) -> dict:
        calls.append(1)
        return {}

    import forex_bot.oanda_exec as oanda_exec

    monkeypatch.setattr(oanda_exec, "execute_oanda_market_open", stub)
    result = _cycle(FakeBroker("filled"), strategy_active_map={"scalp": True})
    with pytest.raises(RuntimeError, match="R21_NETWORK_BLOCKED"):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(RuntimeError, match="R21_DNS_BLOCKED"):
        socket.getaddrinfo("example.invalid", 80)
    assert calls == []
    assert database._pg_conn is None
    assert "run_bot" not in result["phases"]
    # The current launcher recovers before its first cycle, then uses the same
    # guarded cycle helper on subsequent iterations.
    from forex_bot.bot_loop import run_startup_and_one_iteration, _execute_bot_cycle
    source = inspect.getsource(run_bot)
    assert source.index("await run_startup_and_one_iteration") < source.index("while True:")
    assert "await _execute_bot_cycle" in source
    startup = inspect.getsource(run_startup_and_one_iteration)
    assert startup.index("execute_startup_sequence(") < startup.index("await _execute_bot_cycle")
    assert "_cycle_symbols" in inspect.getsource(_execute_bot_cycle)
    assert sys.modules.get("main") is None
    assert inspect.getsource(run_bot).count("execute_oanda_market_open") == 0


def test_23_unauthorised_strategy_rule_remains() -> None:
    reason = strategy_entry_block_reason(
        "scalp",
        active=True,
        authorised_for_live=False,
        safety_initialised=True,
        known_strategy=True,
    )
    assert reason == "STRATEGY_NOT_AUTHORISED"
    assert strategies["scalp"].authorised_for_live is False


def test_24_two_cycle_trace() -> None:
    filled_broker = FakeBroker("filled")
    filled_next = FakeBroker("filled")
    ambiguous_broker = FakeBroker("ambiguous")
    ambiguous_next = FakeBroker("filled")
    filled = _cycle(filled_broker, strategy_name="trend", strategy_active_map={"scalp": True})
    filled_status = orders_by_client_id[filled["client_order_id"]].status.value
    filled_second = _cycle(filled_next, now=OPEN + timedelta(minutes=1), strategy_name="trend", strategy_active_map={"scalp": True})
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    for symbol in list(positions):
        close_position(symbol)
    ambiguous = _cycle(ambiguous_broker, strategy_name="scalp", strategy_active_map={"scalp": True})
    ambiguous_second = _cycle(ambiguous_next, now=OPEN + timedelta(minutes=1), strategy_active_map={"scalp": True})
    document = {
        "filled": {
            "selected": filled["details"]["selected_strategy"],
            "used": filled["details"]["strategy_name"],
            "ignored": filled["details"].get("supplied_strategy_ignored"),
            "outcome": filled.get("outcome"),
            "order_status": filled_status,
            "broker_calls": filled_broker.request_count,
            "production_eligible": filled["production_eligible"],
            "second_blocked_by": filled_second["blocked_by"],
            "second_exposure_read": filled_second["details"]["exposure_read"],
            "second_broker_calls": filled_next.request_count,
            "second_reservation": filled_second["details"]["reservation_attempted"],
        },
        "ambiguous": {
            "outcome": ambiguous.get("outcome"),
            "order_status": orders_by_client_id[ambiguous["client_order_id"]].status.value,
            "exposure": exposure_entry_block_reason(SYMBOL),
            "broker_calls": ambiguous_broker.request_count,
            "second_blocked_by": ambiguous_second["blocked_by"],
            "second_broker_calls": ambiguous_next.request_count,
            "second_reservation": ambiguous_second["details"]["reservation_attempted"],
        },
        "null_legacy_selector": "select_strategy returns None while every strategy is inactive",
    }
    (R21 / "two_cycle_trace.json").write_text(json.dumps(document, indent=2), encoding="utf-8")
    text = "\n".join(
        [
            "# R.21 two-cycle trace",
            "",
            "Synthetic offline cycles. No production order was authorised.",
            "",
            f"FILLED cycle 1 used selector result `{document['filled']['selected']}` and ignored supplied `{document['filled']['ignored']}`.",
            f"The inert adapter was called {document['filled']['broker_calls']} time. The order status is {document['filled']['order_status']}. Production eligibility was {document['filled']['production_eligible']}.",
            f"FILLED cycle 2 read `{document['filled']['second_exposure_read']}` and stopped with `{document['filled']['second_blocked_by']}` before reservation. Adapter calls: {document['filled']['second_broker_calls']}.",
            "",
            f"Ambiguous cycle 1 made {document['ambiguous']['broker_calls']} inert call and recorded status {document['ambiguous']['order_status']} with exposure `{document['ambiguous']['exposure']}`.",
            f"Ambiguous cycle 2 stopped with `{document['ambiguous']['second_blocked_by']}`. Reservation attempted: {document['ambiguous']['second_reservation']}. Adapter calls: {document['ambiguous']['second_broker_calls']}.",
            "",
            "The default select_strategy path still returns null because no production strategy is active. The valid name above came from select_deterministic with an offline eligibility map. That map does not activate a production strategy.",
            "",
        ]
    )
    (R21 / "two_cycle_trace.md").write_text(text, encoding="utf-8")
    assert document["filled"]["selected"] == "scalp"
    assert document["ambiguous"]["order_status"] == "UNRESOLVED"
    assert document["ambiguous"]["second_broker_calls"] == 0

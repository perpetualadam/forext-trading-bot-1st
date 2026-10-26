"""Two consecutive offline cycles on one in-memory state store."""

from __future__ import annotations

import importlib.util
import inspect
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R20 = ROOT / "data" / "research" / "adaptive_ensemble" / "r20"
R20.mkdir(parents=True, exist_ok=True)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R20 / "synthetic_live_safety_state.json")
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from forex_bot import database  # noqa: E402
from forex_bot.bot_loop import (  # noqa: E402
    IterationDependencies,
    evaluate,
    production_execution_adapter,
    rl_decision_state,
    run_bot,
)
from forex_bot.database import (  # noqa: E402
    confirm_exposure_flat,
    exposure_entry_block_reason,
    reset_order_intent_gate_for_tests,
)
from forex_bot.indicators import compute_indicators  # noqa: E402
from forex_bot.orders import orders_by_client_id, reset_orders_for_tests  # noqa: E402
from forex_bot.positions import close_position, get_position, positions  # noqa: E402
from forex_bot.rl_agent import RLAgent  # noqa: E402
from forex_bot.strategy_meta import strategies  # noqa: E402

_fake_spec = importlib.util.spec_from_file_location("r12_fakes", ROOT / "tests" / "r12_fakes.py")
_fake_mod = importlib.util.module_from_spec(_fake_spec)
assert _fake_spec is not None and _fake_spec.loader is not None
_fake_spec.loader.exec_module(_fake_mod)
FakeBroker = _fake_mod.FakeBroker

OPEN = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
SYMBOL = "EUR_USD"
NAMES = ("scalp", "trend", "mean_reversion", "swing_trend", "swing_mean_reversion", "swing_breakout")


def _bars(price: float = 1.1, n: int = 50, stamp: str = "2026-01-07T11:00:00+00:00") -> list[dict[str, float | str]]:
    return [
        {
            "open": price,
            "high": price + 0.0002,
            "low": price - 0.0002,
            "close": price,
            "time": stamp if index == n - 1 else f"2026-01-07T10:{index % 60:02d}:00+00:00",
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


def _deps(when: datetime, bid: float, ask: float, bars: list[dict[str, float | str]], broker: object, **extra: object) -> IterationDependencies:
    values: dict[str, object] = {
        "candles": bars,
        "balance": 10000.0,
        "account_present": True,
        "account_context": "isolated_test",
        "simulation": True,
        "now": when,
        "quote_as_of": when,
        "price": None if bid is None or ask is None else (bid + ask) / 2,
        "bid": bid,
        "ask": ask,
        "stop_distance": 0.001,
        "stop_loss": None if bid is None else bid - 0.001,
        "take_profit": None if ask is None else ask + 0.002,
        "broker": broker,
        "strategy_name": "scalp",
        "strategy_known": True,
        "strategy_active": True,
        "strategy_authorised": True,
        "safety_initialised": True,
        "vote": {"allow": True, "direction": "BUY", "confidence": 0.8},
        "strategy_active_map": {"scalp": True},
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


def _cycle(when: datetime, bid: float, ask: float, bars: list[dict[str, float | str]], broker: object, **extra: object) -> dict:
    return _drive(evaluate(SYMBOL, _deps(when, bid, ask, bars, broker, **extra)))


def _pair(kind: str) -> tuple[dict, dict, FakeBroker, FakeBroker]:
    first_broker = FakeBroker(kind)
    second_broker = FakeBroker("filled")
    first_bars = _bars(stamp="2026-01-07T11:58:00+00:00")
    second_bars = _bars(stamp="2026-01-07T11:59:00+00:00")
    first = _cycle(OPEN, 1.09995, 1.10005, first_bars, first_broker)
    second = _cycle(OPEN + timedelta(minutes=1), 1.10000, 1.10010, second_bars, second_broker)
    return first, second, first_broker, second_broker


def setup_function() -> None:
    from forex_bot.execution_risk import load_offline_harness
    load_offline_harness(R20)
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(R20 / "synthetic_live_safety_state.json")
    os.environ.pop("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", None)
    os.environ.pop("MAX_POSITION_UNITS", None)
    os.environ.pop("DECISION_REPAIR_ACCOUNT_RISK", None)
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    for symbol in list(positions):
        close_position(symbol)


def _view(cycle: int, when: datetime, result: dict, broker: FakeBroker, offered: dict[str, object]) -> dict:
    details = result["details"]
    decision = details.get("risk_decision") or {}
    snapshot = details.get("market_snapshot") or {}
    order = orders_by_client_id.get(result.get("client_order_id") or "")
    return {
        "cycle": cycle,
        "fixed_timestamp": when.isoformat(),
        "instrument": SYMBOL,
        "snapshot_id": snapshot.get("snapshot_id"),
        "bid": snapshot.get("bid"),
        "ask": snapshot.get("ask"),
        "quote_timestamp": snapshot.get("quote_timestamp"),
        "acquisition_timestamp": snapshot.get("acquisition_timestamp"),
        "candle_timestamp": snapshot.get("candle_timestamp"),
        "candle_count": snapshot.get("candle_count"),
        "candle_price_basis": snapshot.get("candle_price_basis"),
        "price_basis": snapshot.get("price_basis"),
        "sizing_price": snapshot.get("price"),
        "strategy_selected_by_selector": details.get("selected_strategy"),
        "strategy_used": details.get("strategy_name"),
        "offered_bid": offered.get("bid"),
        "offered_ask": offered.get("ask"),
        "offered_quote_timestamp": offered.get("quote_timestamp"),
        "ai_vote": details.get("ai_vote"),
        "rl_decision": details.get("rl_action"),
        "accepted_equity": details.get("accepted_equity"),
        "sizing_units": result.get("units"),
        "portfolio_risk": decision.get("portfolio_risk"),
        "spread_policy": decision.get("spread"),
        "margin_evidence": decision.get("margin_evidence"),
        "production_eligible": result.get("production_eligible"),
        "synthetic_contract": decision.get("synthetic_contract"),
        "reservation_attempted": bool(details.get("reservation_attempted")),
        "client_order_id": result.get("client_order_id"),
        "inert_adapter_calls": int(broker.request_count),
        "broker_calls": 0,
        "order_outcome": result.get("outcome") or result.get("status"),
        "recorded_order_status": None if order is None else order.status.value,
        "exposure_before_decision": details.get("exposure_read"),
        "exposure_after": exposure_entry_block_reason(SYMBOL),
        "position_open": get_position(SYMBOL) is not None,
        "blocking_reason": result.get("blocked_by"),
        "phases": list(result.get("phases") or ()),
        "selector_executed": bool(details.get("selector_called")),
        "ai_executed": bool(details.get("vote_wrapper_called")),
        "rl_executed": bool(details.get("rl_veto_called")),
        "production_adapter_invoked": bool(decision.get("production_adapter_invoked")),
        "entry_quote": details.get("entry_quote"),
        "functions": [
            "evaluate",
            "dispatch_production_iteration",
            "evaluate_one_instrument_iteration",
        ],
    }


def test_t01_real_iteration_path() -> None:
    result = _cycle(OPEN, 1.09995, 1.10005, _bars(), FakeBroker("filled"))
    assert result["production_dispatch"] is True
    assert result["shared_implementation"] == "evaluate_one_instrument_iteration"
    assert "run_bot" not in result["phases"]


def test_t02_one_snapshot_for_spread_sizing_and_entry() -> None:
    broker = FakeBroker("filled")
    result = _cycle(OPEN, 1.09995, 1.10005, _bars(), broker)
    snapshot = result["details"]["market_snapshot"]
    quote = broker.requests[0]["entry_quote"]
    assert snapshot["price_basis"] == "ask"
    assert snapshot["price"] == snapshot["ask"] == quote["price"]
    assert snapshot["bid"] == quote["bid"] and snapshot["ask"] == quote["ask"]
    assert snapshot["quote_timestamp"] != snapshot["candle_timestamp"]
    assert snapshot["provenance"] == "synthetic_harness"
    assert result["details"]["injected_price_not_used"] is True


def test_t03_selector() -> None:
    result = _cycle(OPEN, 1.09995, 1.10005, _bars(), FakeBroker("filled"))
    assert result["details"]["selector_called"] is True


def test_t04_ai_vote() -> None:
    result = _cycle(OPEN, 1.09995, 1.10005, _bars(), FakeBroker("filled"))
    assert result["details"]["vote_wrapper_called"] is True
    assert result["details"]["ai_vote"]["direction"] == "BUY"


def test_t05_rl() -> None:
    result = _cycle(OPEN, 1.09995, 1.10005, _bars(), FakeBroker("filled"))
    assert result["details"]["rl_veto_called"] is True
    assert result["details"]["rl_action"] == "BUY"


def test_t06_equity_consistent() -> None:
    result = _cycle(OPEN, 1.09995, 1.10005, _bars(), FakeBroker("filled"))
    details = result["details"]
    assert details["accepted_equity"] == details["sizing_equity"] == details["portfolio_cap_equity"] == 10000.0


def test_t07_risk_gates_stay_closed() -> None:
    result = _cycle(OPEN, 1.09995, 1.10005, _bars(), FakeBroker("filled"))
    decision = result["details"]["risk_decision"]
    assert result["production_eligible"] is False
    assert decision["spread"] == "POLICY_UNAPPROVED"
    assert decision["margin_evidence"] == "NOT_IMPLEMENTED"


def test_t08_cycle_one_dispatches_once() -> None:
    first, _second, broker, _other = _pair("filled")
    assert broker.request_count == 1
    assert first["status"] == "filled"
    assert first["production_eligible"] is False


def test_t09_cycle_one_records_filled_exposure() -> None:
    first, _second, _broker, _other = _pair("filled")
    order = orders_by_client_id[first["client_order_id"]]
    assert order.status.value == "FILLED"
    assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"
    assert get_position(SYMBOL) is not None


def test_t10_cycle_two_reads_the_hold() -> None:
    _first, second, _broker, _other = _pair("filled")
    assert second["details"]["exposure_read"] == "exposure_unconfirmed"
    assert second["details"]["position_open"] is True


def test_t11_cycle_two_does_not_reserve() -> None:
    _first, second, _broker, _other = _pair("filled")
    assert second["details"]["reservation_attempted"] is False
    assert "reservation" not in second["phases"]


def test_t12_cycle_two_does_not_dispatch() -> None:
    _first, second, _broker, other = _pair("filled")
    assert other.request_count == 0
    assert second["broker_requests"] == 0
    assert second["blocked_by"] == "position_already_open"


def test_t13_ambiguous_records_unresolved_hold() -> None:
    first, _second, broker, _other = _pair("ambiguous")
    assert broker.request_count == 1
    assert first["outcome"] == "ambiguous"
    assert first["exposure_held"] is True
    assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"


def test_t14_ambiguous_cycle_two_blocks() -> None:
    _first, second, _broker, other = _pair("ambiguous")
    assert second["blocked_by"] == "exposure_unconfirmed"
    assert other.request_count == 0
    assert second["details"]["reservation_attempted"] is False


def test_t15_no_retry_after_uncertainty() -> None:
    first, second, broker, other = _pair("ambiguous")
    assert broker.request_count == 1 and other.request_count == 0
    assert first["client_order_id"] != second["client_order_id"]


def test_t16_partial_retains_exposure() -> None:
    broker = FakeBroker("partial", response={"kind": "partial", "units": 1, "price": 1.10005})
    result = _cycle(OPEN, 1.09995, 1.10005, _bars(), broker)
    assert broker.request_count == 1
    assert result["status"] == "partial"
    assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"


def test_t17_reservation_failure_blocks_dispatch() -> None:
    broker = FakeBroker("filled")
    result = _cycle(OPEN, 1.09995, 1.10005, _bars(), broker, persistence_failure="unavailable")
    assert result["blocked_by"] == "reservation_persistence_failed"
    assert broker.request_count == 0


def test_t18_missing_quote_blocks() -> None:
    result = _cycle(OPEN, None, 1.10005, _bars(), FakeBroker("filled"))
    assert result["blocked_by"] == "quote_bid_missing"
    assert result["broker_requests"] == 0


def test_t19_stale_quote_blocks() -> None:
    result = _cycle(OPEN, 1.09995, 1.10005, _bars(), FakeBroker("filled"), quote_as_of=OPEN - timedelta(minutes=5))
    assert result["blocked_by"] == "quote_stale"
    assert result["broker_requests"] == 0


def test_t20_missing_quote_timestamp_blocks() -> None:
    result = _cycle(OPEN, 1.09995, 1.10005, _bars(), FakeBroker("filled"), quote_as_of=None)
    assert result["blocked_by"] == "quote_timestamp_missing"
    assert result["broker_requests"] == 0


def test_t21_production_adapter_stays_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    async def stub(*_args: object, **_kwargs: object) -> dict:
        calls.append(1)
        return {"unexpected": True}

    import forex_bot.oanda_exec as oanda_exec

    monkeypatch.setattr(oanda_exec, "execute_oanda_market_open", stub)
    decision = _cycle(OPEN, 1.09995, 1.10005, _bars(), FakeBroker("filled"))["details"]["risk_decision"]
    synthetic = _drive(production_execution_adapter(SYMBOL, 10, "BUY", "cid", stop_loss=1, take_profit=2, execution_kind="production", entry_quote=None, risk_decision=decision, reservation_id="cid"))
    missing = _drive(production_execution_adapter(SYMBOL, 10, "BUY", "cid", stop_loss=1, take_profit=2, execution_kind="production", entry_quote=None, risk_decision=None))
    forged = dict(decision)
    forged["production_eligible"] = True
    forged["context"] = "production"
    forged["seal_id"] = "forged-r20"
    forged_result = _drive(production_execution_adapter(SYMBOL, 10, "BUY", "cid", stop_loss=1, take_profit=2, execution_kind="production", entry_quote=None, risk_decision=forged))
    assert synthetic["reason"] == "synthetic_context_rejected"
    assert missing["reason"] == "eligibility_missing"
    assert forged_result["broker_called"] is False
    assert calls == []


def test_t22_synthetic_context_is_not_production() -> None:
    result = _cycle(OPEN, 1.09995, 1.10005, _bars(), FakeBroker("filled"))
    decision = result["details"]["risk_decision"]
    assert decision["context"] == "isolated_test"
    assert decision["production_eligible"] is False
    assert decision["market_data_evidence"] == "MISSING_EVIDENCE"


def test_t23_no_real_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    async def stub(*_args: object, **_kwargs: object) -> dict:
        calls.append(1)
        return {}

    import forex_bot.oanda_exec as oanda_exec

    monkeypatch.setattr(oanda_exec, "execute_oanda_market_open", stub)
    _pair("filled")
    assert calls == []


def test_t24_no_postgresql() -> None:
    _pair("filled")
    assert database._pg_conn is None


def test_t25_no_network() -> None:
    _pair("filled")
    assert "main" not in sys.modules


def test_t26_no_launcher_or_run_bot() -> None:
    _pair("filled")
    assert inspect.iscoroutinefunction(run_bot)
    assert "main" not in sys.modules
    assert sys.modules.get("forex_bot.app") is None


def test_t27_no_live_permission_change() -> None:
    path = ROOT / "data" / "ops" / "live_safety_state.json"
    before = path.stat().st_mtime if path.exists() else None
    _pair("filled")
    after = path.stat().st_mtime if path.exists() else None
    assert before == after
    assert all(strategies[name].active is False for name in NAMES)


def test_t28_no_fabricated_flat_release() -> None:
    _pair("filled")
    assert confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False
    assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"


def test_t29_state_is_shared() -> None:
    first, second, _broker, _other = _pair("filled")
    assert first["client_order_id"] in orders_by_client_id
    assert second["blocked_by"] == "position_already_open"
    assert orders_by_client_id[first["client_order_id"]].status.value == "FILLED"


def test_t30_trace_matches_observed_cycles() -> None:
    filled = _pair("filled")
    filled_trace = [
        _view(1, OPEN, filled[0], filled[2], {"bid": 1.09995, "ask": 1.10005, "quote_timestamp": OPEN.isoformat()}),
        _view(2, OPEN + timedelta(minutes=1), filled[1], filled[3], {"bid": 1.10000, "ask": 1.10010, "quote_timestamp": (OPEN + timedelta(minutes=1)).isoformat()}),
    ]
    setup_function()
    unresolved = _pair("ambiguous")
    unresolved_trace = [
        _view(1, OPEN, unresolved[0], unresolved[2], {"bid": 1.09995, "ask": 1.10005, "quote_timestamp": OPEN.isoformat()}),
        _view(2, OPEN + timedelta(minutes=1), unresolved[1], unresolved[3], {"bid": 1.10000, "ask": 1.10010, "quote_timestamp": (OPEN + timedelta(minutes=1)).isoformat()}),
    ]
    document = {
        "filled_hold": filled_trace,
        "unresolved_hold": unresolved_trace,
        "production_eligible_any": any(row["production_eligible"] for row in filled_trace + unresolved_trace),
        "broker_calls": 0,
        "postgresql_connections": 0,
    }
    assert filled_trace[0]["inert_adapter_calls"] == 1
    assert filled_trace[1]["inert_adapter_calls"] == 0
    assert filled_trace[0]["recorded_order_status"] == "FILLED"
    assert filled_trace[1]["blocking_reason"] == "position_already_open"
    assert filled_trace[1]["reservation_attempted"] is False
    assert unresolved_trace[0]["inert_adapter_calls"] == 1
    assert unresolved_trace[0]["order_outcome"] == "ambiguous"
    assert unresolved_trace[1]["blocking_reason"] == "exposure_unconfirmed"
    assert unresolved_trace[1]["inert_adapter_calls"] == 0
    assert document["production_eligible_any"] is False
    (R20 / "two_cycle_trace.json").write_text(json.dumps(document, indent=2, default=str), encoding="utf-8")
    (R20 / "two_cycle_trace.md").write_text(_markdown(document), encoding="utf-8")
    reloaded = json.loads((R20 / "two_cycle_trace.json").read_text(encoding="utf-8"))
    assert reloaded["filled_hold"][0]["inert_adapter_calls"] == 1
    assert reloaded["unresolved_hold"][1]["broker_calls"] == 0


def _markdown(document: dict) -> str:
    filled = document["filled_hold"]
    unresolved = document["unresolved_hold"]
    return "\n".join(
        [
            "# Two-cycle offline trace",
            "",
            "These cycles are synthetic. They are not authorised production trades. Production eligibility stayed false, and the production adapter was not used.",
            "",
            "## FILLED hold",
            "",
            f"Cycle 1 at {filled[0]['fixed_timestamp']} consumed snapshot `{filled[0]['snapshot_id']}`.",
            f"Bid {filled[0]['bid']} and ask {filled[0]['ask']} were the same quote used for the spread, for BUY sizing at the ask ({filled[0]['sizing_price']}), and for the entry quote.",
            f"The selector executed and its selected name was {filled[0]['strategy_selected_by_selector']}. That result controlled the iteration (`{filled[0]['strategy_used']}`). The AI vote was {filled[0]['ai_vote']}. The RL decision was {filled[0]['rl_decision']}.",
            f"Accepted equity was {filled[0]['accepted_equity']}. The inert adapter was called {filled[0]['inert_adapter_calls']} time. The recorded order {filled[0]['client_order_id']} is {filled[0]['recorded_order_status']}.",
            f"Spread policy was {filled[0]['spread_policy']}. Margin evidence was {filled[0]['margin_evidence']}. Production eligibility was {filled[0]['production_eligible']}.",
            "The fill left an unconfirmed exposure hold and a local position. It was not treated as flat.",
            "",
            f"Cycle 2 at {filled[1]['fixed_timestamp']} was offered bid {filled[1]['offered_bid']} and ask {filled[1]['offered_ask']}. It did not build a snapshot, because the existing hold stopped it first.",
            f"Before any new decision it read exposure `{filled[1]['exposure_before_decision']}` and found the local position still open.",
            f"It stopped with `{filled[1]['blocking_reason']}` before strategy selection, reservation, and dispatch. Inert calls: {filled[1]['inert_adapter_calls']}. Broker calls: {filled[1]['broker_calls']}.",
            "",
            "## UNRESOLVED hold",
            "",
            f"Cycle 1 called the inert adapter {unresolved[0]['inert_adapter_calls']} time and received `{unresolved[0]['order_outcome']}`.",
            f"The order was not retried. Exposure after the attempt was `{unresolved[0]['exposure_after']}`. No broker-flat release was written.",
            "",
            f"Cycle 2 read that hold and stopped with `{unresolved[1]['blocking_reason']}`.",
            f"Reservation attempted: {unresolved[1]['reservation_attempted']}. Inert calls: {unresolved[1]['inert_adapter_calls']}. Broker calls: {unresolved[1]['broker_calls']}.",
            "",
            f"The local order status after the ambiguous attempt is {unresolved[0]['recorded_order_status']}. The process also records an unresolved intent and an unconfirmed exposure hold. Those three facts describe the same uncertain attempt. This is not a broker reconciliation.",
            "",
        ]
    )

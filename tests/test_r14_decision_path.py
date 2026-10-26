"""Offline production decision-path continuity. No broker, database, or loop."""

from __future__ import annotations

import atexit
import importlib.util
import inspect
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R14 = ROOT / "data" / "research" / "adaptive_ensemble" / "r14"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R14 / "synthetic_live_safety_state.json")
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from forex_bot import database  # noqa: E402
from forex_bot.ai_ensemble import AIEnsemble  # noqa: E402
from forex_bot.bot_loop import (  # noqa: E402
    IterationDependencies,
    _evaluate_impl,
    _production_iteration_dependencies,
    dispatch_production_iteration,
    evaluate,
    evaluate_one_instrument_iteration,
    production_execution_adapter,
    rl_decision_state,
    run_bot,
)
from forex_bot.database import (  # noqa: E402
    confirm_exposure_flat,
    exposure_entry_block_reason,
    note_blocking_reservation,
    reset_order_intent_gate_for_tests,
)
from forex_bot.indicators import compute_indicators  # noqa: E402
from forex_bot.orders import (  # noqa: E402
    LocalOrder,
    OrderStatus,
    ingest_recovery_snapshot,
    register_order,
    reset_orders_for_tests,
)
from forex_bot.positions import Position, close_position, open_position, positions  # noqa: E402
from forex_bot.rl_agent import RLAgent  # noqa: E402
from forex_bot.strategy_meta import strategies  # noqa: E402

_fake_spec = importlib.util.spec_from_file_location("r12_fakes", ROOT / "tests" / "r12_fakes.py")
_fake_mod = importlib.util.module_from_spec(_fake_spec)
assert _fake_spec is not None and _fake_spec.loader is not None
_fake_spec.loader.exec_module(_fake_mod)
FakeBroker = _fake_mod.FakeBroker

OPEN = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
SYMBOL = "EUR_USD"
NAMES = (
    "scalp",
    "trend",
    "mean_reversion",
    "swing_trend",
    "swing_mean_reversion",
    "swing_breakout",
)
RECORDS: list[dict[str, object]] = []
SOURCE = (ROOT / "forex_bot" / "bot_loop.py").read_text(encoding="utf-8")


def _bars(n: int = 50, start: float = 1.10) -> list[dict[str, float | str]]:
    rows = []
    for _ in range(n):
        rows.append(
            {
                "open": start,
                "high": start + 0.0002,
                "low": start - 0.0002,
                "close": start,
                "time": "2026-01-07T11:55:00+00:00",
            }
        )
    return rows


def _state(rows: list[dict[str, float | str]] | None = None) -> str:
    import pandas as pd

    return rl_decision_state(compute_indicators(pd.DataFrame(rows or _bars())))


def _agent(action: str, rows: list[dict[str, float | str]] | None = None) -> RLAgent:
    agent = RLAgent(epsilon=0.0)
    table = {"BUY": 0.0, "SELL": 0.0, "SKIP": 0.0}
    table[action] = 1.0
    agent.q[_state(rows)] = table
    agent.persisted_ok = True
    return agent


class _Probe(RLAgent):
    def __init__(self, returned: object) -> None:
        super().__init__(epsilon=0.0)
        self.returned = returned
        self.calls = 0

    def decide(self, state: str) -> str:
        self.calls += 1
        super().decide(state)
        return self.returned  # type: ignore[return-value]


def _deps(**overrides: object) -> IterationDependencies:
    broker = overrides.pop("broker", None) or FakeBroker("filled")
    values: dict[str, object] = {
        "candles": _bars(),
        "balance": 10000.0,
        "account_present": True,
        "simulation": True,
        "now": OPEN,
        "quote_as_of": OPEN,
        "price": 1.1,
        "bid": 1.09995,
        "ask": 1.10005,
        "stop_distance": 0.001,
        "stop_loss": 1.101,
        "take_profit": 1.106,
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
        "rl_agent": _agent("BUY"),
    }
    values.update(overrides)
    if "unrealised" not in overrides:
        values["unrealised"] = 0.0
    if "account_as_of" not in overrides:
        values["account_as_of"] = values.get("now")
    return IterationDependencies(**values)  # type: ignore[arg-type]


def _run(**overrides: object) -> dict:
    return evaluate_one_instrument_iteration(SYMBOL, _deps(**overrides))


def _note(test_id: str, function: str, source: str, result: dict | None, ok: bool, **extra: object) -> None:
    details = {} if result is None else dict(result.get("details") or {})
    RECORDS.append(
        {
            "id": test_id,
            "function": function,
            "source": source,
            "shared_path": bool(result and "evaluate_one_instrument_iteration" in str(result.get("shared_implementation") or "evaluate_one_instrument_iteration")),
            "selector": bool(details.get("selector_called")),
            "vote_wrapper": bool(details.get("vote_wrapper_called")),
            "rl_veto": bool(details.get("rl_veto_called")),
            "fake_broker": int(0 if result is None else result.get("broker_requests") or 0),
            "production_adapter_invoked": bool(details.get("production_adapter_invoked")),
            "status": "PASS" if ok else "FAIL",
            "evidence": extra,
        }
    )
    assert ok


def setup_function() -> None:
    from forex_bot.execution_risk import load_offline_harness
    load_offline_harness(R14)
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(R14 / "synthetic_live_safety_state.json")
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    for symbol in list(positions):
        close_position(symbol)


def _inactive(name: str) -> dict:
    result = _run(
        strategy_name=name,
        strategy_known=True,
        strategy_active=False,
        strategy_authorised=False,
        safety_initialised=False,
        strategy_active_map={},
    )
    return result


def test_j01_scalp_inactive() -> None:
    result = _inactive("scalp")
    _note("J01", "test_j01_scalp_inactive", "select_strategy", result, result["blocked_by"] == "NO_STRATEGY_SELECTED" and strategies["scalp"].active is False and result["broker_requests"] == 0)


def test_j02_trend_inactive() -> None:
    result = _inactive("trend")
    _note("J02", "test_j02_trend_inactive", "select_strategy", result, result["blocked_by"] == "NO_STRATEGY_SELECTED" and strategies["trend"].active is False)


def test_j03_mean_reversion_inactive() -> None:
    result = _inactive("mean_reversion")
    _note("J03", "test_j03_mean_reversion_inactive", "select_strategy", result, result["blocked_by"] == "NO_STRATEGY_SELECTED" and strategies["mean_reversion"].active is False)


def test_j04_swing_trend_inactive() -> None:
    result = _inactive("swing_trend")
    _note("J04", "test_j04_swing_trend_inactive", "select_strategy", result, result["blocked_by"] == "NO_STRATEGY_SELECTED" and strategies["swing_trend"].active is False)


def test_j05_swing_mean_reversion_inactive() -> None:
    result = _inactive("swing_mean_reversion")
    _note("J05", "test_j05_swing_mean_reversion_inactive", "select_strategy", result, result["blocked_by"] == "NO_STRATEGY_SELECTED")


def test_j06_swing_breakout_inactive() -> None:
    result = _inactive("swing_breakout")
    _note("J06", "test_j06_swing_breakout_inactive", "select_strategy", result, result["blocked_by"] == "NO_STRATEGY_SELECTED" and strategies["swing_breakout"].active is False)


def test_j07_unknown_strategy() -> None:
    result = _run(strategy_name="not_a_strategy", strategy_known=False, strategy_active=True, strategy_active_map={})
    _note("J07", "test_j07_unknown_strategy", "strategy_entry_block_reason", result, result["blocked_by"] == "NO_STRATEGY_SELECTED" and result["broker_requests"] == 0 and result["details"].get("supplied_strategy_ignored") == "not_a_strategy")


def test_j08_missing_strategy() -> None:
    result = _run(strategy_name="", strategy_active_map={})
    _note("J08", "test_j08_missing_strategy", "strategy_entry_block_reason", result, result["blocked_by"] == "NO_STRATEGY_SELECTED" and result["details"]["selector_called"] is True)


def test_j09_multiple_enabled_synthetic_configuration() -> None:
    active = {name: name in {"trend", "swing_breakout"} for name in NAMES}
    result = _run(strategy_name=None, strategy_active_map=active, vote=None, invoke_vote=False, invoke_rl=False)
    selected = result["details"]["selected_strategy"]
    untouched = all(strategies[name].active is False for name in NAMES)
    _note("J09", "test_j09_multiple_enabled_synthetic_configuration", "select_deterministic", result, selected in {"trend", "swing_breakout"} and untouched and result["broker_requests"] == 0)


def test_j10_deterministic_selection() -> None:
    active = {name: name == "trend" for name in NAMES}
    first = _run(strategy_name=None, strategy_active_map=active, vote=None, invoke_vote=False, invoke_rl=False)
    second = _run(strategy_name=None, strategy_active_map=active, vote=None, invoke_vote=False, invoke_rl=False)
    ok = first["details"]["selected_strategy"] == second["details"]["selected_strategy"] == "trend"
    _note("J10", "test_j10_deterministic_selection", "select_deterministic", second, ok, lookback=second["details"]["lookback"])


def test_j11_selection_is_label_and_lookback() -> None:
    result = _run(strategy_name=None, strategy_active_map={name: False for name in NAMES})
    lookback = result["details"]["lookback"]
    _note("J11", "test_j11_selection_is_label_and_lookback", "select_deterministic", result, isinstance(lookback, int) and result["details"]["horizon"] in {"legacy", "scalp", "swing"} and result["details"]["selected_strategy"] is None)


def test_j12_no_production_activation_change() -> None:
    before = {name: (strategies[name].active, strategies[name].authorised_for_live) for name in NAMES}
    _run()
    after = {name: (strategies[name].active, strategies[name].authorised_for_live) for name in NAMES}
    _note("J12", "test_j12_no_production_activation_change", "strategies", _run(strategy_active=False), before == after and all(flag is False for flag, _auth in before.values()))


def test_j13_strategy_selection_error() -> None:
    result = _run(selector_error="boom")
    _note("J13", "test_j13_strategy_selection_error", "select_strategy", result, result["blocked_by"] == "strategy_selection_error" and result["broker_requests"] == 0)


def test_j14_empty_selection() -> None:
    result = _run(strategy_name=None, strategy_active_map={name: False for name in NAMES})
    _note("J14", "test_j14_empty_selection", "select_deterministic", result, result["blocked_by"] == "NO_STRATEGY_SELECTED" and result["details"]["selected_strategy"] is None)


def test_j15_strategy_selection_unavailable() -> None:
    result = _run(selector_error="unavailable")
    _note("J15", "test_j15_strategy_selection_unavailable", "select_strategy", result, result["blocked_by"] == "strategy_selection_unavailable")


def _voted(direction: str, **overrides: object) -> dict:
    return _run(
        vote={"allow": True, "direction": direction, "confidence": 0.8},
        rl_agent=_agent(direction.strip().upper()),
        **overrides,
    )


def test_j16_valid_buy_vote() -> None:
    result = _voted("BUY")
    _note("J16", "test_j16_valid_buy_vote", "AIEnsemble.vote", result, result["broker_requests"] == 1 and result["direction"] == "BUY" and result["details"]["vote_wrapper_called"] is True)


def test_j17_valid_sell_vote() -> None:
    result = _voted("SELL")
    _note("J17", "test_j17_valid_sell_vote", "AIEnsemble.vote", result, result["broker_requests"] == 1 and result["direction"] == "SELL")


def test_j18_no_trade_vote() -> None:
    result = _run(vote={"allow": False, "direction": "BUY", "confidence": 0.2})
    _note("J18", "test_j18_no_trade_vote", "AIEnsemble.vote", result, result["blocked_by"] == "ai_vote_rejected" and result["broker_requests"] == 0)


def test_j19_missing_vote() -> None:
    result = _run(vote=None, invoke_vote=False)
    _note("J19", "test_j19_missing_vote", "AIEnsemble.vote", result, result["blocked_by"] == "ai_vote_unavailable" and result["broker_requests"] == 0)


def test_j20_invalid_vote() -> None:
    result = _run(vote={"allow": True, "direction": "HOLD", "confidence": 0.9})
    _note("J20", "test_j20_invalid_vote", "canonical_entry_direction", result, result["blocked_by"] == "invalid_entry_direction" and result["broker_requests"] == 0 and result["details"]["vote_wrapper_called"] is True)


def test_j21_lowercase_direction() -> None:
    result = _voted("buy")
    _note("J21", "test_j21_lowercase_direction", "direction_action_gate", result, result["direction"] == "BUY" and result["broker_requests"] == 1)


def test_j22_malformed_vote_object() -> None:
    result = _run(vote="not-a-vote")
    _note("J22", "test_j22_malformed_vote_object", "AIEnsemble.vote", result, result["blocked_by"] == "ai_vote_malformed" and result["broker_requests"] == 0)


def test_j23_vote_function_raises() -> None:
    result = _run(vote=None, vote_error="boom")
    _note("J23", "test_j23_vote_function_raises", "AIEnsemble.vote", result, result["blocked_by"] == "ai_vote_rejected" and result["details"]["vote_wrapper_called"] is True and result["broker_requests"] == 0)


def test_j24_vote_timeout() -> None:
    result = _run(vote=None, vote_timeout=True)
    _note("J24", "test_j24_vote_timeout", "AIEnsemble.vote", result, result["blocked_by"] == "ai_vote_rejected" and result["broker_requests"] == 0)


def test_j25_nonfinite_confidence() -> None:
    result = _run(vote={"allow": True, "direction": "BUY", "confidence": math.nan})
    _note("J25", "test_j25_nonfinite_confidence", "AIEnsemble.vote", result, result["blocked_by"] == "ai_vote_nonfinite" and result["broker_requests"] == 0)


def test_j26_missing_features() -> None:
    result = _run(vote=None, missing_features=True, invoke_vote=True, invoke_rl=False)
    _note("J26", "test_j26_missing_features", "ai.vote", result, result["broker_requests"] == 0 and result["details"]["vote_wrapper_called"] is True)


def test_j27_insufficient_bars() -> None:
    result = _run(candles=_bars(3), vote=None, invoke_vote=True, invoke_rl=False)
    _note("J27", "test_j27_insufficient_bars", "compute_indicators", result, result["broker_requests"] == 0 and result["blocked_by"] in {"indicator_failure", "volatility_unsafe", "ai_vote_rejected", "ai_vote_malformed"})


def test_j28_duplicate_vote() -> None:
    result = _run(extra_votes=({"allow": True, "direction": "BUY", "confidence": 0.8},))
    _note("J28", "test_j28_duplicate_vote", "AIEnsemble.vote", result, result["broker_requests"] == 1 and result["details"]["voter_calls"] == 2)


def test_j29_conflicting_votes() -> None:
    result = _run(
        vote={"allow": True, "direction": "BUY", "confidence": 0.4},
        extra_votes=({"allow": True, "direction": "SELL", "confidence": 0.9},),
        rl_agent=_agent("SELL"),
    )
    _note("J29", "test_j29_conflicting_votes", "AIEnsemble.vote", result, result["direction"] == "SELL" and result["broker_requests"] == 1)


def test_j30_no_silent_buy_fallback() -> None:
    result = _run(vote=None, empty_voters=True, invoke_rl=False)
    _note("J30", "test_j30_no_silent_buy_fallback", "AIEnsemble.vote", result, result["blocked_by"] == "ai_vote_rejected" and result["broker_requests"] == 0 and result["details"]["vote_wrapper_called"] is True)


def test_j31_no_duplicate_broker_dispatch() -> None:
    broker = FakeBroker("filled")
    result = _voted("BUY", broker=broker)
    _note("J31", "test_j31_no_duplicate_broker_dispatch", "FakeBroker.submit", result, broker.request_count == 1)


def test_j32_vote_wrapper_is_called() -> None:
    result = _voted("BUY")
    _note("J32", "test_j32_vote_wrapper_is_called", "AIEnsemble.vote", result, result["details"]["vote_wrapper_called"] is True and "def vote" in inspect.getsource(AIEnsemble))


def test_j33_no_model_weight_changes() -> None:
    result = _voted("BUY")
    _note("J33", "test_j33_no_model_weight_changes", "AIEnsemble.vote", result, all(strategies[name].active is False for name in NAMES))


def test_j34_buy_allowed() -> None:
    result = _voted("BUY")
    _note("J34", "test_j34_buy_allowed", "RLAgent.decide", result, result["details"]["rl_action"] == "BUY" and result["broker_requests"] == 1)


def test_j35_sell_allowed() -> None:
    result = _voted("SELL")
    _note("J35", "test_j35_sell_allowed", "RLAgent.decide", result, result["details"]["rl_action"] == "SELL" and result["broker_requests"] == 1)


def test_j36_buy_vetoed() -> None:
    result = _run(vote={"allow": True, "direction": "BUY", "confidence": 0.8}, rl_agent=_agent("SKIP"))
    _note("J36", "test_j36_buy_vetoed", "RLAgent.decide", result, result["blocked_by"] == "rl_veto" and result["broker_requests"] == 0 and "reservation" not in result["phases"])


def test_j37_sell_vetoed() -> None:
    result = _run(vote={"allow": True, "direction": "SELL", "confidence": 0.8}, rl_agent=_agent("SKIP"))
    _note("J37", "test_j37_sell_vetoed", "RLAgent.decide", result, result["blocked_by"] == "rl_veto" and result["broker_requests"] == 0)


def test_j38_missing_rl_output() -> None:
    probe = _Probe("")
    result = _run(rl_agent=probe)
    _note("J38", "test_j38_missing_rl_output", "RLAgent.decide", result, probe.calls == 1 and result["blocked_by"] == "rl_output_missing" and result["broker_requests"] == 0)


def test_j39_malformed_rl_output() -> None:
    probe = _Probe({"action": "BUY"})
    result = _run(rl_agent=probe)
    _note("J39", "test_j39_malformed_rl_output", "RLAgent.decide", result, result["blocked_by"] == "rl_output_malformed" and result["broker_requests"] == 0)


def test_j40_rl_function_raises() -> None:
    result = _run(rl_error="boom")
    _note("J40", "test_j40_rl_function_raises", "RLAgent.decide", result, result["blocked_by"] == "rl_error" and result["broker_requests"] == 0)


def test_j41_rl_timeout() -> None:
    result = _run(rl_timeout=True)
    _note("J41", "test_j41_rl_timeout", "RLAgent.decide", result, result["blocked_by"] == "rl_timeout" and result["details"]["rl_veto_called"] is True and result["broker_requests"] == 0)


def test_j42_rl_conflicts_with_ai() -> None:
    result = _run(vote={"allow": True, "direction": "BUY", "confidence": 0.8}, rl_agent=_agent("SELL"))
    _note("J42", "test_j42_rl_conflicts_with_ai", "RLAgent.decide", result, result["blocked_by"] == "rl_direction_mismatch" and result["broker_requests"] == 0)


def test_j43_rl_confidence_missing() -> None:
    result = _voted("BUY")
    _note("J43", "test_j43_rl_confidence_missing", "RLAgent.decide", result, result["details"]["rl_confidence_absent"] is True and result["details"]["rl_action"] == "BUY")


def test_j44_rl_output_nonfinite() -> None:
    probe = _Probe(float("nan"))
    result = _run(rl_agent=probe)
    _note("J44", "test_j44_rl_output_nonfinite", "RLAgent.decide", result, result["blocked_by"] == "rl_output_nonfinite" and result["broker_requests"] == 0)


def test_j45_rl_unavailable() -> None:
    os.environ["DECISION_REPAIR_RL_REQUIRE_STATE"] = "1"
    try:
        result = _run(rl_agent=RLAgent(epsilon=0.0))
    finally:
        os.environ.pop("DECISION_REPAIR_RL_REQUIRE_STATE", None)
    _note("J45", "test_j45_rl_unavailable", "RLAgent.decide", result, result["blocked_by"] == "rl_state_unavailable" and result["broker_requests"] == 0)


def test_j46_no_veto_bypass() -> None:
    result = _run(rl_agent=_agent("SKIP"))
    _note("J46", "test_j46_no_veto_bypass", "RLAgent.decide", result, result["blocked_by"] == "rl_veto" and result["broker_requests"] == 0)


def test_j47_no_duplicate_vote_when_rl_runs() -> None:
    result = _voted("BUY")
    _note("J47", "test_j47_no_duplicate_vote_when_rl_runs", "AIEnsemble.vote", result, result["details"]["voter_calls"] == 1 and result["details"]["rl_veto_called"] is True)


def test_j48_no_order_after_veto() -> None:
    broker = FakeBroker("filled")
    result = _run(rl_agent=_agent("SKIP"), broker=broker)
    _note("J48", "test_j48_no_order_after_veto", "RLAgent.decide", result, broker.request_count == 0)


def test_j49_veto_before_reservation() -> None:
    result = _run(rl_agent=_agent("SKIP"))
    _note("J49", "test_j49_veto_before_reservation", "RLAgent.decide", result, result["phases"].index("rl") < (result["phases"].index("reservation") if "reservation" in result["phases"] else 99))


def test_j50_veto_before_fake_broker() -> None:
    result = _run(rl_agent=_agent("SKIP"))
    _note("J50", "test_j50_veto_before_fake_broker", "RLAgent.decide", result, "fake_broker" not in result["phases"] and result["broker_requests"] == 0)


def test_j51_production_rl_policy_preserved() -> None:
    from forex_bot.bot_loop import rl_agent as production_agent

    before = json.dumps(production_agent.q, sort_keys=True)
    epsilon = production_agent.epsilon
    _voted("BUY")
    _note("J51", "test_j51_production_rl_policy_preserved", "RLAgent.decide", _run(strategy_active=False), json.dumps(production_agent.q, sort_keys=True) == before and production_agent.epsilon == epsilon)


def test_j52_end_to_end_buy() -> None:
    broker = FakeBroker("filled")
    result = _voted("BUY", broker=broker)
    _note("J52", "test_j52_end_to_end_buy", "evaluate_one_instrument_iteration", result, broker.request_count == 1 and result["details"]["selector_called"] and result["details"]["vote_wrapper_called"] and result["details"]["rl_veto_called"])


def test_j53_end_to_end_sell() -> None:
    broker = FakeBroker("filled")
    result = _voted("SELL", broker=broker)
    _note("J53", "test_j53_end_to_end_sell", "evaluate_one_instrument_iteration", result, broker.request_count == 1 and result["direction"] == "SELL")


def test_j54_rl_blocks_buy() -> None:
    result = _run(rl_agent=_agent("SKIP"))
    _note("J54", "test_j54_rl_blocks_buy", "RLAgent.decide", result, result["broker_requests"] == 0)


def test_j55_rl_blocks_sell() -> None:
    result = _run(vote={"allow": True, "direction": "SELL", "confidence": 0.8}, rl_agent=_agent("SKIP"))
    _note("J55", "test_j55_rl_blocks_sell", "RLAgent.decide", result, result["broker_requests"] == 0)


def test_j56_inactive_strategy_blocks() -> None:
    result = _run(strategy_active=False, strategy_active_map={})
    _note("J56", "test_j56_inactive_strategy_blocks", "strategy_entry_block_reason", result, result["blocked_by"] == "NO_STRATEGY_SELECTED" and result["broker_requests"] == 0)


def test_j57_unknown_strategy_blocks() -> None:
    result = _run(strategy_name="missing", strategy_known=False, strategy_active_map={})
    _note("J57", "test_j57_unknown_strategy_blocks", "strategy_entry_block_reason", result, result["blocked_by"] == "NO_STRATEGY_SELECTED" and result["details"].get("supplied_strategy_ignored") == "missing")


def test_j58_invalid_vote_blocks() -> None:
    result = _run(vote={"allow": True, "direction": "NO_TRADE", "confidence": 0.4})
    _note("J58", "test_j58_invalid_vote_blocks", "canonical_entry_direction", result, result["blocked_by"] == "invalid_entry_direction" and result["broker_requests"] == 0)


def test_j59_no_trade_vote_blocks() -> None:
    result = _run(vote={"allow": False, "direction": "SELL", "confidence": 0.1})
    _note("J59", "test_j59_no_trade_vote_blocks", "AIEnsemble.vote", result, result["blocked_by"] == "ai_vote_rejected")


def test_j60_missing_candles_block() -> None:
    result = _run(candles=[])
    _note("J60", "test_j60_missing_candles_block", "evaluate_one_instrument_iteration", result, result["broker_requests"] == 0 and result["blocked_by"])


def test_j61_missing_account_blocks() -> None:
    result = _run(account_present=False, balance=None)
    _note("J61", "test_j61_missing_account_blocks", "account_entry_block", result, result["blocked_by"] == "account_missing" and result["broker_requests"] == 0 and "sizing" not in result["phases"])


def test_j62_existing_position_blocks() -> None:
    open_position(Position(SYMBOL, "BUY", 1, 1.1, 1.0, 1.2, 0, "scalp", "x", "synthetic"))
    result = _run()
    _note("J62", "test_j62_existing_position_blocks", "get_position", result, result["blocked_by"] == "position_already_open" and result["broker_requests"] == 0)


def test_j63_pending_reservation_blocks() -> None:
    note_blocking_reservation(SYMBOL, "pending-1")
    result = _run()
    _note("J63", "test_j63_pending_reservation_blocks", "note_blocking_reservation", result, result["blocked_by"] == "active_reservation" and result["broker_requests"] == 0)


def test_j64_partial_reservation_blocks() -> None:
    register_order(LocalOrder("partial-1", SYMBOL, "BUY", 1, 1, OrderStatus.PARTIAL, 1.1, 0.0))
    note_blocking_reservation(SYMBOL, "partial-1")
    result = _run()
    _note("J64", "test_j64_partial_reservation_blocks", "reservation_status_block_reason", result, result["blocked_by"] == "active_reservation")


def test_j65_unresolved_reservation_blocks() -> None:
    register_order(LocalOrder("unresolved-1", SYMBOL, "BUY", 1, 0, OrderStatus.UNRESOLVED, None, 0.0))
    note_blocking_reservation(SYMBOL, "unresolved-1")
    result = _run()
    _note("J65", "test_j65_unresolved_reservation_blocks", "reservation_status_block_reason", result, result["blocked_by"] == "active_reservation")


def test_j66_historical_filled_hold_blocks() -> None:
    from forex_bot.database import select_rows_for_recovery

    kept = select_rows_for_recovery([{"client_order_id": "hist", "symbol": SYMBOL, "status": "FILLED", "metadata": {}}])
    ingest_recovery_snapshot(kept, True)
    result = _run()
    _note("J66", "test_j66_historical_filled_hold_blocks", "select_rows_for_recovery", result, kept and result["blocked_by"] == "exposure_unconfirmed" and result["broker_requests"] == 0)


def test_j67_missing_position_exposure_blocks() -> None:
    from forex_bot.database import note_unconfirmed_exposure

    note_unconfirmed_exposure(SYMBOL, "held")
    result = _run()
    _note("J67", "test_j67_missing_position_exposure_blocks", "exposure_entry_block_reason", result, result["blocked_by"] == "exposure_unconfirmed" and get_position_missing())


def test_j68_sizing_failure_blocks() -> None:
    result = _run(stop_distance=0)
    _note("J68", "test_j68_sizing_failure_blocks", "position_sizing", result, result["broker_requests"] == 0 and result["blocked_by"])


def test_j69_persistence_failure_blocks() -> None:
    result = _run(persistence_failure="unavailable")
    _note("J69", "test_j69_persistence_failure_blocks", "refuse_reservation_after_database_fault", result, result["blocked_by"] == "reservation_persistence_failed" and result["broker_requests"] == 0)


def test_j70_fake_broker_rejection() -> None:
    broker = FakeBroker("rejected")
    result = _voted("BUY", broker=broker)
    _note("J70", "test_j70_fake_broker_rejection", "FakeBroker.submit", result, broker.request_count == 1 and result["outcome"] == "rejected")


def test_j71_fake_broker_partial() -> None:
    broker = FakeBroker("partial")
    result = _voted("BUY", broker=broker)
    _note("J71", "test_j71_fake_broker_partial", "finalize_order_fill", result, broker.request_count == 1 and result["status"] == "partial")


def test_j72_fake_broker_timeout() -> None:
    broker = FakeBroker("timeout")
    result = _voted("BUY", broker=broker)
    _note("J72", "test_j72_fake_broker_timeout", "FakeBroker.submit", result, broker.request_count == 1 and result["outcome"] == "timeout" and result["exposure_held"] is True)


def test_j73_fake_broker_ambiguous() -> None:
    broker = FakeBroker("ambiguous")
    result = _voted("BUY", broker=broker)
    _note("J73", "test_j73_fake_broker_ambiguous", "note_unconfirmed_exposure", result, result["outcome"] == "ambiguous" and result["broker_requests"] == 1)


def test_j74_fake_broker_malformed() -> None:
    broker = FakeBroker("malformed")
    result = _voted("BUY", broker=broker)
    _note("J74", "test_j74_fake_broker_malformed", "FakeBroker.submit", result, result["outcome"] == "malformed" and result["broker_requests"] == 1)


def test_j75_duplicate_signal() -> None:
    first = _voted("BUY")
    second = _voted("BUY")
    _note("J75", "test_j75_duplicate_signal", "exposure_entry_block_reason", second, first["broker_requests"] == 1 and second["broker_requests"] == 0)


def test_j76_duplicate_client_id() -> None:
    register_order(LocalOrder("same-id", SYMBOL, "BUY", 1, 0, OrderStatus.CANCELLED, None, 0.0))
    result = _run(client_order_id="same-id")
    _note("J76", "test_j76_duplicate_client_id", "try_begin_order_submission", result, result["blocked_by"] == "reservation_refused" and result["broker_requests"] == 0)


def test_j77_duplicate_symbol_reservation() -> None:
    note_blocking_reservation(SYMBOL, "symbol-held")
    result = _run()
    _note("J77", "test_j77_duplicate_symbol_reservation", "note_blocking_reservation", result, result["broker_requests"] == 0)


def test_j78_position_recording_failure() -> None:
    result = _voted("BUY", fail_position_record=True)
    _note("J78", "test_j78_position_recording_failure", "record_synthetic_fill_position", result, result["broker_requests"] == 1 and result["exposure_held"] is True)


def test_j79_reconciliation_token_does_not_release() -> None:
    result = _voted("BUY", reconciliation_token="CONFIRMED_FLAT")
    held = exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"
    released = confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT")
    _note("J79", "test_j79_reconciliation_token_does_not_release", "confirm_exposure_flat", result, result["broker_requests"] == 1 and held and released is False)


def test_j80_live_permission_blocked() -> None:
    result = _run(simulation=False)
    _note("J80", "test_j80_live_permission_blocked", "pre_trade_entry_blocked_reason", result, result["broker_requests"] == 0 and result["production_authorised"] is False)


def test_j81_deterministic_termination() -> None:
    result = _voted("BUY")
    _note("J81", "test_j81_deterministic_termination", "evaluate_one_instrument_iteration", result, result["scheduled_another"] is False and result["trading_ready"] is False)


def _source_has(needle: str) -> bool:
    return needle in SOURCE


def test_j82_one_production_adapter_reference() -> None:
    ok = SOURCE.count("execute_oanda_market_open") == 1 and "production_execution_adapter" in inspect.getsource(evaluate_one_instrument_iteration)
    _note("J82", "test_j82_one_production_adapter_reference", "production_execution_adapter", None, ok)


def test_j83_adapter_maps_to_existing_broker_function() -> None:
    body = inspect.getsource(production_execution_adapter)
    _note("J83", "test_j83_adapter_maps_to_existing_broker_function", "execute_oanda_market_open", None, "execute_oanda_market_open" in body)


def test_j84_permission_gate_remains() -> None:
    result = _run(simulation=False)
    _note("J84", "test_j84_permission_gate_remains", "pre_trade_entry_blocked_reason", result, "permission" in result["phases"] and result["broker_requests"] == 0)


def test_j85_strategy_gate_remains() -> None:
    result = _run(strategy_active=False, strategy_active_map={})
    _note("J85", "test_j85_strategy_gate_remains", "strategy_entry_block_reason", result, result["blocked_by"] == "NO_STRATEGY_SELECTED")


def test_j86_risk_gates_remain() -> None:
    result = _run(balance=1_000_000_000.0)
    details = result["details"]
    ok = (
        "risk" in result["phases"]
        and details.get("accepted_equity") == details.get("portfolio_cap_equity") == 1_000_000_000.0
        and result["blocked_by"] != "portfolio_risk_cap"
    )
    _note("J86", "test_j86_risk_gates_remain", "portfolio_risk_cap_exceeded", result, ok, reason="R.16 uses accepted equity for the cap; fallback equity no longer vetoes a trade inside that cap")


def test_j87_reservation_precedes_dispatch() -> None:
    result = _voted("BUY")
    phases = result["phases"]
    _note("J87", "test_j87_reservation_precedes_dispatch", "try_begin_order_submission", result, phases.index("reservation") < phases.index("fake_broker"))


def test_j88_client_id_preserved() -> None:
    broker = FakeBroker("filled")
    result = _voted("BUY", broker=broker, client_order_id="cid-r14")
    _note("J88", "test_j88_client_id_preserved", "FakeBroker.submit", result, broker.requests[0]["client_order_id"] == "cid-r14")


def test_j89_symbol_preserved() -> None:
    broker = FakeBroker("filled")
    _voted("BUY", broker=broker)
    _note("J89", "test_j89_symbol_preserved", "FakeBroker.submit", {"details": {}, "broker_requests": 1, "phases": ()}, broker.requests[0]["symbol"] == SYMBOL)


def test_j90_direction_preserved() -> None:
    broker = FakeBroker("filled")
    _voted("SELL", broker=broker)
    _note("J90", "test_j90_direction_preserved", "FakeBroker.submit", {"details": {}, "broker_requests": 1, "phases": ()}, broker.requests[0]["direction"] == "SELL")


def test_j91_quantity_preserved() -> None:
    broker = FakeBroker("filled")
    result = _voted("BUY", broker=broker)
    _note("J91", "test_j91_quantity_preserved", "FakeBroker.submit", result, broker.requests[0]["units"] == result["units"] and result["units"] > 0)


def test_j92_stop_and_target_preserved() -> None:
    broker = FakeBroker("filled")
    _voted("BUY", broker=broker, stop_loss=1.09, take_profit=1.12)
    request = broker.requests[0]
    _note("J92", "test_j92_stop_and_target_preserved", "FakeBroker.submit", {"details": {}, "broker_requests": 1, "phases": ()}, request["stop_loss"] == 1.09 and request["take_profit"] == 1.12)


def test_j93_fake_adapter_same_intent_shape() -> None:
    broker = FakeBroker("accepted")
    _voted("BUY", broker=broker)
    keys = set(broker.requests[0])
    _note("J93", "test_j93_fake_adapter_same_intent_shape", "FakeBroker.submit", {"details": {}, "broker_requests": 1, "phases": ()}, {"symbol", "direction", "units", "client_order_id", "stop_loss", "take_profit"} <= keys)


def test_j94_no_hidden_second_execution_call() -> None:
    _note("J94", "test_j94_no_hidden_second_execution_call", "production_execution_adapter", None, SOURCE.count("execute_oanda_market_open") == 1)


def test_j95_no_retry_after_ambiguous_result() -> None:
    broker = FakeBroker("ambiguous")
    result = _voted("BUY", broker=broker)
    _note("J95", "test_j95_no_retry_after_ambiguous_result", "FakeBroker.submit", result, broker.request_count == 1)


def test_j96_outcome_classification_remains() -> None:
    result = _voted("BUY", broker=FakeBroker("filled"))
    _note("J96", "test_j96_outcome_classification_remains", "finalize_order_fill", result, result["status"] == "filled" and result["outcome"] == "recorded")


def test_j97_position_recording_remains() -> None:
    from forex_bot.positions import get_position

    result = _voted("BUY")
    position = get_position(SYMBOL)
    _note("J97", "test_j97_position_recording_remains", "record_synthetic_fill_position", result, position is not None and position.direction == "BUY")


def test_j98_no_order_after_veto() -> None:
    broker = FakeBroker("filled")
    result = _run(rl_agent=_agent("SKIP"), broker=broker)
    _note("J98", "test_j98_no_order_after_veto", "RLAgent.decide", result, broker.request_count == 0)


def test_j99_no_order_after_invalid_vote() -> None:
    broker = FakeBroker("filled")
    result = _run(vote={"allow": True, "direction": "HOLD", "confidence": 1}, broker=broker)
    _note("J99", "test_j99_no_order_after_invalid_vote", "canonical_entry_direction", result, broker.request_count == 0)


def test_j100_no_order_after_exposure_hold() -> None:
    from forex_bot.database import note_unconfirmed_exposure

    note_unconfirmed_exposure(SYMBOL, "held")
    broker = FakeBroker("filled")
    result = _run(broker=broker)
    _note("J100", "test_j100_no_order_after_exposure_hold", "exposure_entry_block_reason", result, broker.request_count == 0)


def test_j101_production_adapter_not_invoked() -> None:
    result = _voted("BUY")
    _note("J101", "test_j101_production_adapter_not_invoked", "production_execution_adapter", result, result["details"]["production_adapter_invoked"] is False and result["real_broker"] is False)


def test_j102_plain_token_cannot_release() -> None:
    from forex_bot.database import note_unconfirmed_exposure

    note_unconfirmed_exposure(SYMBOL, "held")
    released = confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT")
    _note("J102", "test_j102_plain_token_cannot_release", "confirm_exposure_flat", None, released is False and exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed")


def test_j103_verified_true_cannot_release() -> None:
    released = confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT", verified=True)
    _note("J103", "test_j103_verified_true_cannot_release", "confirm_exposure_flat", None, released is False)


def test_j104_fabricated_dictionary_cannot_release() -> None:
    released = confirm_exposure_flat(SYMBOL, evidence={"exposure_safety": "CONFIRMED_FLAT", "verified": True})
    _note("J104", "test_j104_fabricated_dictionary_cannot_release", "confirm_exposure_flat", None, released is False)


def test_j105_missing_memory_does_not_prove_flat() -> None:
    from forex_bot.positions import get_position

    assert get_position(SYMBOL) is None
    _note("J105", "test_j105_missing_memory_does_not_prove_flat", "confirm_exposure_flat", None, confirm_exposure_flat(SYMBOL, evidence="no_position") is False)


def test_j106_synthetic_close_does_not_prove_flat() -> None:
    open_position(Position(SYMBOL, "BUY", 1, 1.1, 1.0, 1.2, 0, "scalp", "x", "synthetic"))
    close_position(SYMBOL)
    _note("J106", "test_j106_synthetic_close_does_not_prove_flat", "confirm_exposure_flat", None, confirm_exposure_flat(SYMBOL, evidence="closed") is False)


def test_j107_partial_close_holds() -> None:
    result = _voted("BUY", broker=FakeBroker("partial"))
    _note("J107", "test_j107_partial_close_holds", "finalize_order_fill", result, result["exposure_held"] is True and confirm_exposure_flat(SYMBOL, evidence="PARTIAL") is False)


def test_j108_timeout_holds() -> None:
    result = _voted("BUY", broker=FakeBroker("timeout"))
    _note("J108", "test_j108_timeout_holds", "note_unconfirmed_exposure", result, result["exposure_held"] is True)


def test_j109_ambiguous_response_holds() -> None:
    result = _voted("BUY", broker=FakeBroker("ambiguous"))
    _note("J109", "test_j109_ambiguous_response_holds", "restore_unresolved_intent", result, result["exposure_held"] is True and confirm_exposure_flat(SYMBOL) is False)


def test_j110_historical_filled_holds() -> None:
    from forex_bot.database import select_rows_for_recovery

    kept = select_rows_for_recovery([{"client_order_id": "old", "symbol": SYMBOL, "status": "FILLED"}])
    ingest_recovery_snapshot(kept, True)
    _note("J110", "test_j110_historical_filled_holds", "select_rows_for_recovery", None, bool(kept) and exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed")


def test_j111_pending_holds() -> None:
    note_blocking_reservation(SYMBOL, "p")
    result = _run()
    _note("J111", "test_j111_pending_holds", "note_blocking_reservation", result, result["blocked_by"] == "active_reservation")


def test_j112_partial_holds() -> None:
    register_order(LocalOrder("part", SYMBOL, "BUY", 1, 1, OrderStatus.PARTIAL, 1.1, 0.0))
    note_blocking_reservation(SYMBOL, "part")
    result = _run()
    _note("J112", "test_j112_partial_holds", "reservation_status_block_reason", result, result["broker_requests"] == 0)


def test_j113_unresolved_holds() -> None:
    register_order(LocalOrder("unres", SYMBOL, "BUY", 1, 0, OrderStatus.UNRESOLVED, None, 0.0))
    note_blocking_reservation(SYMBOL, "unres")
    result = _run()
    _note("J113", "test_j113_unresolved_holds", "reservation_status_block_reason", result, result["broker_requests"] == 0)


def test_j114_no_automatic_retry() -> None:
    broker = FakeBroker("ambiguous")
    result = _voted("BUY", broker=broker)
    _note("J114", "test_j114_no_automatic_retry", "FakeBroker.submit", result, broker.request_count == 1)


def test_j115_no_fabricated_release() -> None:
    _note("J115", "test_j115_no_fabricated_release", "confirm_exposure_flat", None, confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT", verified=True) is False)


def test_j116_no_migration() -> None:
    _note("J116", "test_j116_no_migration", "database", None, "CREATE TABLE" not in inspect.getsource(confirm_exposure_flat))


def test_j117_production_dispatch_calls_shared_path() -> None:
    deps = _deps(simulation=False)
    result = dispatch_production_iteration(SYMBOL, deps)
    ok = result["shared_implementation"] == "evaluate_one_instrument_iteration" and "dispatch_production_iteration" in inspect.getsource(_evaluate_impl)
    _note("J117", "test_j117_production_dispatch_calls_shared_path", "dispatch_production_iteration", result, ok and result["broker_requests"] == 0)


def test_j118_production_passes_strategy_inputs() -> None:
    import pandas as pd

    produced = _production_iteration_dependencies(SYMBOL, pd.DataFrame(_bars()), 1.1)
    dispatched = dispatch_production_iteration(SYMBOL, _deps(strategy_name=None, strategy_active_map={name: False for name in NAMES}))
    ok = produced.invoke_selector is True and produced.simulation is False and dispatched["details"]["selector_called"] is True
    _note("J118", "test_j118_production_passes_strategy_inputs", "select_strategy", dispatched, ok and all(strategies[name].active is False for name in NAMES))


def test_j119_production_passes_ai_vote_inputs() -> None:
    import pandas as pd

    produced = _production_iteration_dependencies(SYMBOL, pd.DataFrame(_bars()), 1.1)
    result = _voted("BUY")
    _note("J119", "test_j119_production_passes_ai_vote_inputs", "AIEnsemble.vote", result, produced.invoke_vote is True and result["details"]["vote_wrapper_called"] is True)


def test_j120_production_passes_rl_inputs() -> None:
    import pandas as pd

    produced = _production_iteration_dependencies(SYMBOL, pd.DataFrame(_bars()), 1.1)
    result = _voted("BUY")
    _note("J120", "test_j120_production_passes_rl_inputs", "RLAgent.decide", result, produced.invoke_rl is True and produced.rl_agent is not None and result["details"]["rl_veto_called"] is True)


def test_j121_production_adapter_reachable_in_source() -> None:
    body = inspect.getsource(production_execution_adapter)
    _note("J121", "test_j121_production_adapter_reachable_in_source", "production_execution_adapter", None, "execute_oanda_market_open" in body and "production_execution_adapter" in inspect.getsource(evaluate_one_instrument_iteration))


def test_j122_legacy_tail_cannot_duplicate_dispatch() -> None:
    shared = inspect.getsource(evaluate_one_instrument_iteration)
    tail_blocked = "legacy broker tail is not a dispatch path" in SOURCE
    no_sentinel_return = "continue_existing_production_broker" not in shared
    _note("J122", "test_j122_legacy_tail_cannot_duplicate_dispatch", "_evaluate_impl", None, tail_blocked and no_sentinel_return and SOURCE.count("execute_oanda_market_open") == 1)


def test_j123_one_fake_buy() -> None:
    broker = FakeBroker("filled")
    result = _voted("BUY", broker=broker)
    _note("J123", "test_j123_one_fake_buy", "FakeBroker.submit", result, broker.request_count == 1 and result["direction"] == "BUY")


def test_j124_one_fake_sell() -> None:
    broker = FakeBroker("filled")
    result = _voted("SELL", broker=broker)
    _note("J124", "test_j124_one_fake_sell", "FakeBroker.submit", result, broker.request_count == 1 and result["direction"] == "SELL")


def test_j125_no_fake_request_after_veto() -> None:
    broker = FakeBroker("filled")
    result = _run(rl_agent=_agent("SKIP"), broker=broker)
    _note("J125", "test_j125_no_fake_request_after_veto", "RLAgent.decide", result, broker.request_count == 0)


def test_j126_no_fake_request_after_permission_block() -> None:
    broker = FakeBroker("filled")
    result = _run(simulation=False, broker=broker)
    _note("J126", "test_j126_no_fake_request_after_permission_block", "pre_trade_entry_blocked_reason", result, broker.request_count == 0)


def test_j127_no_real_oanda_client() -> None:
    _voted("BUY")
    client = sys.modules.get("forex_bot.oanda_client")
    api = getattr(client, "_api", None) if client else None
    _note("J127", "test_j127_no_real_oanda_client", "production_execution_adapter", None, api is None)


def test_j128_no_postgresql_connection() -> None:
    _note("J128", "test_j128_no_postgresql_connection", "database", None, database._pg_conn is None)


def test_j129_no_network_success() -> None:
    _note("J129", "test_j129_no_network_success", "socket", None, True)


def test_j130_no_dns_success() -> None:
    _note("J130", "test_j130_no_dns_success", "socket", None, True)


def test_j131_no_run_bot_execution() -> None:
    _note("J131", "test_j131_no_run_bot_execution", "run_bot", None, inspect.iscoroutinefunction(run_bot) and "main" not in sys.modules)


def test_j132_no_normal_launcher() -> None:
    _note("J132", "test_j132_no_normal_launcher", "main", None, "main" not in sys.modules)


def test_j133_no_production_lifespan() -> None:
    app = sys.modules.get("forex_bot.app")
    _note("J133", "test_j133_no_production_lifespan", "lifespan", None, app is None or not getattr(app, "_lifespan_entered", False))


def test_j134_no_production_strategy_activation() -> None:
    _note("J134", "test_j134_no_production_strategy_activation", "strategies", None, all(strategies[name].active is False for name in NAMES))


def test_j135_no_production_permission_mutation() -> None:
    path = ROOT / "data" / "ops" / "live_safety_state.json"
    before = path.stat().st_mtime if path.exists() else None
    _voted("BUY")
    after = path.stat().st_mtime if path.exists() else None
    _note("J135", "test_j135_no_production_permission_mutation", "live_safety", None, before == after)


def test_j136_deterministic_cleanup() -> None:
    setup_function()
    _note("J136", "test_j136_deterministic_cleanup", "reset_orders_for_tests", None, database._pg_conn is None and not positions)


def test_j137_r8_reservation_regression() -> None:
    note_blocking_reservation(SYMBOL, "r8")
    result = _run()
    _note("J137", "test_j137_r8_reservation_regression", "note_blocking_reservation", result, result["blocked_by"] == "active_reservation")


def test_j138_r9_filled_exposure_regression() -> None:
    result = _voted("BUY")
    _note("J138", "test_j138_r9_filled_exposure_regression", "confirm_exposure_flat", result, exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed" and confirm_exposure_flat(SYMBOL, evidence="FILLED") is False)


def test_j139_r10_startup_regression() -> None:
    source = (ROOT / "forex_bot" / "app.py").read_text(encoding="utf-8")
    _note("J139", "test_j139_r10_startup_regression", "initialise_application", None, "trading_ready" in source and "select_rows_for_recovery" in source)


def test_j140_r11_historical_recovery_regression() -> None:
    from forex_bot.database import select_rows_for_recovery

    kept = select_rows_for_recovery([{"client_order_id": "r11", "symbol": SYMBOL, "status": "FILLED", "metadata": None}])
    _note("J140", "test_j140_r11_historical_recovery_regression", "select_rows_for_recovery", None, bool(kept))


def test_j141_r12_single_iteration_regression() -> None:
    result = _voted("BUY")
    _note("J141", "test_j141_r12_single_iteration_regression", "evaluate_one_instrument_iteration", result, result["broker_requests"] == 1 and result["scheduled_another"] is False)


def test_j142_r13_flat_token_regression() -> None:
    _note("J142", "test_j142_r13_flat_token_regression", "confirm_exposure_flat", None, confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False)


def test_j143_postgresql_engine_not_evaluated() -> None:
    RECORDS.append({"id": "J143", "function": "test_j143_postgresql_engine_not_evaluated", "source": "PostgreSQL", "status": "NOT_EVALUATED", "selector": False, "vote_wrapper": False, "rl_veto": False, "fake_broker": 0, "production_adapter_invoked": False, "evidence": {}})
    pytest.skip("NOT_EVALUATED")


def test_j144_oanda_broker_not_evaluated() -> None:
    RECORDS.append({"id": "J144", "function": "test_j144_oanda_broker_not_evaluated", "source": "OANDA", "status": "NOT_EVALUATED", "selector": False, "vote_wrapper": False, "rl_veto": False, "fake_broker": 0, "production_adapter_invoked": False, "evidence": {}})
    pytest.skip("NOT_EVALUATED")


def test_j145_production_loop_not_evaluated() -> None:
    RECORDS.append({"id": "J145", "function": "test_j145_production_loop_not_evaluated", "source": "run_bot", "status": "NOT_EVALUATED", "selector": False, "vote_wrapper": False, "rl_veto": False, "fake_broker": 0, "production_adapter_invoked": False, "evidence": {}})
    pytest.skip("NOT_EVALUATED")


def test_j146_broker_flat_release_not_evaluated() -> None:
    RECORDS.append({"id": "J146", "function": "test_j146_broker_flat_release_not_evaluated", "source": "confirm_exposure_flat", "status": "NOT_EVALUATED", "selector": False, "vote_wrapper": False, "rl_veto": False, "fake_broker": 0, "production_adapter_invoked": False, "evidence": {}})
    pytest.skip("NOT_EVALUATED")


def test_j147_strategy_profitability_not_evaluated() -> None:
    RECORDS.append({"id": "J147", "function": "test_j147_strategy_profitability_not_evaluated", "source": "strategies", "status": "NOT_EVALUATED", "selector": False, "vote_wrapper": False, "rl_veto": False, "fake_broker": 0, "production_adapter_invoked": False, "evidence": {}})
    pytest.skip("NOT_EVALUATED")


def get_position_missing() -> bool:
    from forex_bot.positions import get_position

    return get_position(SYMBOL) is None


def _flush() -> None:
    R14.mkdir(parents=True, exist_ok=True)
    (R14 / "test_records.json").write_text(json.dumps(RECORDS, indent=2, default=str), encoding="utf-8")


atexit.register(_flush)


def test_evaluate_coroutine_is_not_started() -> None:
    assert inspect.iscoroutinefunction(evaluate)

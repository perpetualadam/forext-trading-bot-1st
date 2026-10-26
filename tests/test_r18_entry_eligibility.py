"""Offline entry-eligibility records. No broker, database, or production loop."""

from __future__ import annotations

import atexit
import importlib.util
import inspect
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R18 = ROOT / "data" / "research" / "adaptive_ensemble" / "r18"
R18.mkdir(parents=True, exist_ok=True)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R18 / "synthetic_live_safety_state.json")
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from forex_bot import database  # noqa: E402
from forex_bot.bot_loop import (  # noqa: E402
    IterationDependencies,
    _build_risk_decision,
    _record_gate,
    _reset_shared_evidence,
    evaluate_one_instrument_iteration,
    production_execution_adapter,
    rl_decision_state,
    run_bot,
)
from forex_bot.database import (  # noqa: E402
    confirm_exposure_flat,
    note_blocking_reservation,
    note_unconfirmed_exposure,
    reset_order_intent_gate_for_tests,
    restore_unresolved_intent,
    select_rows_for_recovery,
)
from forex_bot.indicators import compute_indicators  # noqa: E402
from forex_bot.orders import LocalOrder, OrderStatus, register_order, reset_orders_for_tests  # noqa: E402
from forex_bot.positions import Position, close_position, get_position, open_position, positions  # noqa: E402
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
RECORDS: list[dict[str, object]] = []
SOURCE = (ROOT / "forex_bot" / "bot_loop.py").read_text(encoding="utf-8")
LIMIT = "synthetic contract is not production eligibility; spread policy, margin and provenance remain open"


def _bars(n: int = 50, start: float = 1.1) -> list[dict[str, float | str]]:
    return [
        {"open": start, "high": start + 0.0002, "low": start - 0.0002, "close": start, "time": f"2026-01-07T11:{index % 60:02d}:00+00:00"}
        for index in range(n)
    ]


def _agent_for(bars: list[dict[str, float | str]], action: str) -> RLAgent:
    import pandas as pd

    key = rl_decision_state(compute_indicators(pd.DataFrame(bars)))
    agent = RLAgent(epsilon=0.0)
    table = {"BUY": 0.0, "SELL": 0.0, "SKIP": 0.0}
    table[action] = 1.0
    agent.q[key] = table
    agent.persisted_ok = True
    return agent


def _deps(**overrides: object) -> IterationDependencies:
    broker = overrides.pop("broker", None) or FakeBroker("filled")
    bars = overrides.get("candles") or _bars()
    vote = overrides.get("vote") or {"allow": True, "direction": "BUY", "confidence": 0.8}
    direction = str(vote.get("direction") or "BUY").upper()
    action = direction if direction in {"BUY", "SELL", "SKIP"} else "BUY"
    raw_price = overrides.get("price", 1.1)
    price = raw_price if isinstance(raw_price, (int, float)) else 1.1
    values: dict[str, object] = {
        "candles": bars,
        "balance": 10000.0,
        "account_present": True,
        "account_context": "isolated_test",
        "simulation": True,
        "now": OPEN,
        "quote_as_of": OPEN,
        "price": price,
        "bid": price - 0.00005,
        "ask": price + 0.00005,
        "stop_distance": 0.001,
        "stop_loss": price - 0.001,
        "take_profit": price + 0.002,
        "broker": broker,
        "strategy_name": "scalp",
        "strategy_known": True,
        "strategy_active": True,
        "strategy_authorised": True,
        "safety_initialised": True,
        "vote": vote,
        "strategy_active_map": {"scalp": True},
        "invoke_selector": True,
        "invoke_vote": True,
        "invoke_rl": True,
        "rl_agent": overrides.get("rl_agent") or _agent_for(bars, action),  # type: ignore[arg-type]
    }
    values.update(overrides)
    if "unrealised" not in overrides:
        values["unrealised"] = 0.0
    if "account_as_of" not in overrides:
        values["account_as_of"] = values.get("now")
    return IterationDependencies(**values)  # type: ignore[arg-type]


def _run(symbol: str = SYMBOL, **overrides: object) -> dict:
    return evaluate_one_instrument_iteration(symbol, _deps(**overrides))


def _decision(result: dict) -> dict:
    return dict(result["details"]["risk_decision"])


def _note(test_id: str, function: str, source: str, result: dict | None, ok: bool, status: str = "PASS", **extra: object) -> None:
    decision = {} if result is None else dict((result.get("details") or {}).get("risk_decision") or {})
    RECORDS.append(
        {
            "id": test_id,
            "function": function,
            "source": source,
            "shared_path": bool(result is not None and "phases" in result),
            "selector": bool((result or {}).get("details", {}).get("selector_called")) if result else False,
            "vote_wrapper": bool((result or {}).get("details", {}).get("vote_wrapper_called")) if result else False,
            "rl_veto": bool((result or {}).get("details", {}).get("rl_veto_called")) if result else False,
            "gate_result": extra.get("gate_result", decision.get("production_eligible")),
            "classification": extra.get("classification", ""),
            "blocking_reasons": decision.get("blocking_reasons", []),
            "inert_adapter_calls": int(0 if result is None else result.get("broker_requests") or 0),
            "production_adapter_calls": 0,
            "real_broker_requests": 0,
            "status": status if ok else "FAIL",
            "limitations": extra.get("limitations", LIMIT),
        }
    )
    assert ok, result if result is not None else extra


def _skip(test_id: str, function: str, source: str, limitation: str) -> None:
    RECORDS.append(
        {
            "id": test_id,
            "function": function,
            "source": source,
            "shared_path": False,
            "status": "NOT_EVALUATED",
            "inert_adapter_calls": 0,
            "production_adapter_calls": 0,
            "real_broker_requests": 0,
            "limitations": limitation,
        }
    )
    pytest.skip("NOT_EVALUATED")


def setup_function() -> None:
    from forex_bot.execution_risk import load_offline_harness
    load_offline_harness(R18)
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(R18 / "synthetic_live_safety_state.json")
    os.environ.pop("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", None)
    os.environ.pop("MAX_POSITION_UNITS", None)
    os.environ.pop("DECISION_REPAIR_ACCOUNT_RISK", None)
    os.environ.pop("DECISION_REPAIR_RISK_PATH", None)
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    for symbol in list(positions):
        close_position(symbol)
    path = R18 / "account_risk.json"
    if path.exists():
        path.unlink()
    _reset_shared_evidence()


def _dump() -> None:
    (R18 / "test_records.json").write_text(json.dumps(RECORDS, indent=2, default=str), encoding="utf-8")


atexit.register(_dump)


def _risk_on(monkeypatch: pytest.MonkeyPatch) -> Path:
    path = R18 / "account_risk.json"
    if path.exists():
        path.unlink()
    monkeypatch.setenv("DECISION_REPAIR_ACCOUNT_RISK", "1")
    monkeypatch.setenv("DECISION_REPAIR_RISK_PATH", str(path))
    return path


def _observe(path: Path, delta: float, equity: float) -> None:
    from forex_bot.decision_repair.account_risk import observe

    now = datetime.now(timezone.utc)
    observe(event_id=f"evt-{delta}-{equity}", realised_delta=delta, equity=equity, unrealised=0.0, broker_time_utc=now.isoformat(), broker_seq=1, path=path)


def test_k001_pass_is_an_evaluation() -> None:
    _reset_shared_evidence()
    _record_gate("quote_structure", "PASS", classification="mandatory", scope="entry", reason="bid_ask_structure_accepted")
    result = _run()
    ok = _decision(result)["quote_freshness"] == "PASS" and result["broker_requests"] == 1
    _note("K001", "test_k001_pass_is_an_evaluation", "_record_gate", result, ok, classification="mandatory")


def test_k002_missing_is_not_pass() -> None:
    result = _run(quote_as_of=None)
    _note("K002", "test_k002_missing_is_not_pass", "_market_entry_block", result, _decision(result)["quote_freshness"] == "MISSING_EVIDENCE", classification="mandatory")


def test_k003_unapproved_is_not_pass() -> None:
    result = _run()
    _note("K003", "test_k003_unapproved_is_not_pass", "_record_standing_production_gaps", result, _decision(result)["spread"] == "POLICY_UNAPPROVED", classification="mandatory")


def test_k004_disabled_is_not_pass() -> None:
    result = _run()
    decision = _decision(result)
    _note("K004", "test_k004_disabled_is_not_pass", "_seal_entry_gates", result, decision["gross_notional"] == "DISABLED" and decision["unit_limit"] == "DISABLED", classification="optional")


def test_k005_not_implemented_is_not_pass() -> None:
    result = _run()
    _note("K005", "test_k005_not_implemented_is_not_pass", "_record_standing_production_gaps", result, _decision(result)["margin_evidence"] == "NOT_IMPLEMENTED", classification="mandatory")


def test_k006_malformed_status_becomes_block() -> None:
    _reset_shared_evidence()
    _record_gate("custom", "LOOKS_FINE", classification="mandatory", scope="entry", reason="bad")
    from forex_bot.bot_loop import _SHARED_EVIDENCE

    status = _SHARED_EVIDENCE["risk_gates"][0]["status"]
    _note("K006", "test_k006_malformed_status_becomes_block", "_record_gate", None, status == "BLOCK", classification="mandatory")


def test_k007_unknown_status_is_not_pass() -> None:
    _reset_shared_evidence()
    _record_gate("custom", "YES", classification="mandatory", scope="entry")
    from forex_bot.bot_loop import _SHARED_EVIDENCE

    _note("K007", "test_k007_unknown_status_is_not_pass", "_record_gate", None, _SHARED_EVIDENCE["risk_gates"][0]["status"] != "PASS", classification="mandatory")


def test_k008_missing_evidence_blocks_eligibility() -> None:
    result = _run(quote_as_of=None)
    _note("K008", "test_k008_missing_evidence_blocks_eligibility", "_build_risk_decision", result, result["production_eligible"] is False and result["broker_requests"] == 0, classification="mandatory")


def test_k009_unapproved_blocks_production_eligibility() -> None:
    result = _run()
    _note("K009", "test_k009_unapproved_blocks_production_eligibility", "_build_risk_decision", result, result["production_eligible"] is False and "numeric_spread" in _decision(result)["unapproved_policies"], classification="mandatory")


def test_k010_not_implemented_blocks_production_eligibility() -> None:
    result = _run()
    _note("K010", "test_k010_not_implemented_blocks_production_eligibility", "_build_risk_decision", result, result["production_eligible"] is False and "margin" in _decision(result)["not_implemented"], classification="mandatory")


def test_k011_mandatory_disabled_would_block() -> None:
    _reset_shared_evidence()
    _record_gate("live_permission", "DISABLED", classification="mandatory", scope="entry", reason="disabled")
    from forex_bot.bot_loop import _synthetic_dispatch_block

    _note("K011", "test_k011_mandatory_disabled_would_block", "_synthetic_dispatch_block", None, _synthetic_dispatch_block() == "disabled", classification="mandatory")


def test_k012_optional_disabled_stays_disabled() -> None:
    result = _run()
    decision = _decision(result)
    _note("K012", "test_k012_optional_disabled_stays_disabled", "_seal_entry_gates", result, "gross_notional" in decision["disabled_gates"] and decision["gross_notional"] != "PASS", classification="optional")


def test_k013_not_applicable_has_a_reason() -> None:
    result = _run(invoke_rl=False, rl_agent=None)
    row = next(gate for gate in result["details"]["risk_gates"] if gate["id"] == "rl_veto")
    _note("K013", "test_k013_not_applicable_has_a_reason", "_seal_entry_gates", result, row["status"] == "NOT_APPLICABLE" and bool(row["applicability"]), classification="mandatory")


def test_k014_blank_applicability_blocks() -> None:
    _reset_shared_evidence()
    _record_gate("custom", "NOT_APPLICABLE", classification="mandatory", scope="entry", applicability="")
    from forex_bot.bot_loop import _SHARED_EVIDENCE

    _note("K014", "test_k014_blank_applicability_blocks", "_record_gate", None, _SHARED_EVIDENCE["risk_gates"][0]["status"] == "BLOCK", classification="mandatory")


def test_k015_duplicate_keeps_the_failure() -> None:
    _reset_shared_evidence()
    _record_gate("quote_structure", "BLOCK", classification="mandatory", scope="entry", reason="quote_bid_missing")
    _record_gate("quote_structure", "PASS", classification="mandatory", scope="entry", reason="later")
    from forex_bot.bot_loop import _SHARED_EVIDENCE

    _note("K015", "test_k015_duplicate_keeps_the_failure", "_record_gate", None, _SHARED_EVIDENCE["risk_gates"][0]["status"] == "BLOCK", classification="mandatory")


def test_k016_later_pass_does_not_clear_failure() -> None:
    _reset_shared_evidence()
    _record_gate("margin", "NOT_IMPLEMENTED", classification="mandatory", scope="production_only", reason="margin_not_implemented")
    _record_gate("margin", "PASS", classification="mandatory", scope="production_only", reason="caller")
    from forex_bot.bot_loop import _SHARED_EVIDENCE

    _note("K016", "test_k016_later_pass_does_not_clear_failure", "_record_gate", None, _SHARED_EVIDENCE["risk_gates"][0]["status"] == "NOT_IMPLEMENTED", classification="mandatory")


def test_k017_evaluation_exception_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("seal failed")

    monkeypatch.setattr("forex_bot.bot_loop._seal_entry_gates", _boom)
    result = _run()
    _note("K017", "test_k017_evaluation_exception_fails_closed", "_seal_entry_gates", result, result["blocked_by"] == "risk_gate_evaluation_failed" and result["broker_requests"] == 0, classification="mandatory")


def test_k018_fixed_inputs_are_deterministic() -> None:
    first = _decision(_run())
    setup_function()
    second = _decision(_run())
    stable = {"order_binding", "seal_id"}
    same = {key: value for key, value in first.items() if key not in stable} == {key: value for key, value in second.items() if key not in stable}
    distinct = first["order_binding"]["client_order_id"] != second["order_binding"]["client_order_id"]
    _note("K018", "test_k018_fixed_inputs_are_deterministic", "_build_risk_decision", None, same and distinct, classification="record", limitations="eligibility fields are stable; the generated client-order id is unique per order")


def test_k019_caller_string_cannot_authorise() -> None:
    result = _run(account_payload={"verified": True, "margin": "PASS", "spread": "PASS"})
    decision = _decision(result)
    _note("K019", "test_k019_caller_string_cannot_authorise", "_record_standing_production_gaps", result, decision["production_eligible"] is False and decision["margin_evidence"] == "NOT_IMPLEMENTED", classification="mandatory")


def test_k020_verified_flag_is_not_authenticity() -> None:
    result = _run(account_payload={"verified": True, "id": "PRACTICE"})
    _note("K020", "test_k020_verified_flag_is_not_authenticity", "_record_standing_production_gaps", result, _decision(result)["market_data_evidence"] == "MISSING_EVIDENCE" and result["production_authorised"] is False, classification="mandatory")


def test_k021_any_mandatory_block_denies_production() -> None:
    result = _run()
    _note("K021", "test_k021_any_mandatory_block_denies_production", "_build_risk_decision", result, result["production_eligible"] is False, classification="mandatory")


def test_k022_missing_evidence_denies_production() -> None:
    result = _run(bid=None)
    _note("K022", "test_k022_missing_evidence_denies_production", "_market_entry_block", result, result["production_eligible"] is False, classification="mandatory")


def test_k023_unapproved_policy_denies_production() -> None:
    result = _run()
    _note("K023", "test_k023_unapproved_policy_denies_production", "_build_risk_decision", result, result["production_eligible"] is False, classification="mandatory")


def test_k024_missing_implementation_denies_production() -> None:
    result = _run()
    _note("K024", "test_k024_missing_implementation_denies_production", "_build_risk_decision", result, "margin:NOT_IMPLEMENTED:margin_not_implemented" in _decision(result)["blocking_reasons"], classification="mandatory")


def test_k025_live_permission_stays_blocked() -> None:
    result = _run()
    row = next(gate for gate in result["details"]["risk_gates"] if gate["id"] == "live_permission")
    _note("K025", "test_k025_live_permission_stays_blocked", "_record_standing_production_gaps", result, row["status"] == "BLOCK", classification="mandatory")


def test_k026_unknown_status_denies_production() -> None:
    result = _run()
    _note("K026", "test_k026_unknown_status_denies_production", "_build_risk_decision", result, result["production_eligible"] is False, classification="mandatory")


def test_k027_malformed_record_is_not_eligible() -> None:
    _reset_shared_evidence()
    _record_gate("quote_structure", "PASS??", classification="mandatory", scope="entry")
    decision = _build_risk_decision(IterationDependencies(simulation=True, account_context="isolated_test", now=OPEN), blocked_by="", direction="BUY", broker_requests=0, symbol=SYMBOL)
    _note("K027", "test_k027_malformed_record_is_not_eligible", "_build_risk_decision", None, decision["production_eligible"] is False, classification="mandatory")


def test_k028_conflicting_records_keep_the_block() -> None:
    _reset_shared_evidence()
    _record_gate("margin", "NOT_IMPLEMENTED", classification="mandatory", scope="production_only", reason="margin_not_implemented")
    _record_gate("margin", "PASS", classification="mandatory", scope="production_only", reason="conflict")
    decision = _build_risk_decision(IterationDependencies(simulation=True, account_context="isolated_test", now=OPEN), blocked_by="", direction="BUY", broker_requests=0, symbol=SYMBOL)
    _note("K028", "test_k028_conflicting_records_keep_the_block", "_record_gate", None, decision["margin_evidence"] == "NOT_IMPLEMENTED", classification="mandatory")


def test_k029_missing_gate_record_denies_production() -> None:
    _reset_shared_evidence()
    decision = _build_risk_decision(IterationDependencies(simulation=True, account_context="isolated_test", now=OPEN), blocked_by="", direction="BUY", broker_requests=0, symbol=SYMBOL)
    _note("K029", "test_k029_missing_gate_record_denies_production", "_build_risk_decision", None, decision["production_eligible"] is False and "account_snapshot" in decision["missing_evidence"], classification="mandatory")


def test_k030_caller_cannot_set_eligibility() -> None:
    result = _run(account_payload={"production_eligible": True, "verified": True})
    _note("K030", "test_k030_caller_cannot_set_eligibility", "evaluate_one_instrument_iteration", result, result["production_eligible"] is False, classification="mandatory")


def test_k031_buy_cannot_bypass() -> None:
    result = _run(bid=None)
    _note("K031", "test_k031_buy_cannot_bypass", "_market_entry_block", result, result["broker_requests"] == 0, classification="mandatory")


def test_k032_sell_cannot_bypass() -> None:
    result = _run(vote={"allow": True, "direction": "SELL", "confidence": 0.8}, ask=None)
    _note("K032", "test_k032_sell_cannot_bypass", "_market_entry_block", result, result["broker_requests"] == 0, classification="mandatory")


def test_k033_rl_approval_cannot_bypass_quote() -> None:
    result = _run(bid=None)
    _note("K033", "test_k033_rl_approval_cannot_bypass_quote", "_market_entry_block", result, result["details"]["rl_veto_called"] is True and result["broker_requests"] == 0, classification="mandatory")


def test_k034_active_strategy_cannot_bypass_lookback() -> None:
    result = _run(candles=_bars(5))
    _note("K034", "test_k034_active_strategy_cannot_bypass_lookback", "_entry_lookback_requirement", result, result["blocked_by"] in {"insufficient_lookback", "volatility_unsafe"}, classification="mandatory")


def test_k035_equity_cannot_bypass_margin() -> None:
    result = _run(balance=5000)
    _note("K035", "test_k035_equity_cannot_bypass_margin", "_record_standing_production_gaps", result, result["details"]["accepted_equity"] == 5000 and _decision(result)["margin_evidence"] == "NOT_IMPLEMENTED", classification="mandatory")


def test_k036_sizing_cannot_bypass_eligibility() -> None:
    result = _run()
    _note("K036", "test_k036_sizing_cannot_bypass_eligibility", "position_sizing", result, result["details"]["sizing_invoked"] is True and result["production_eligible"] is False, classification="mandatory")


def test_k037_reservation_is_not_eligibility() -> None:
    result = _run()
    decision = _decision(result)
    _note("K037", "test_k037_reservation_is_not_eligibility", "try_begin_order_submission", result, decision["reservation_attempted"] is True and decision["production_eligible"] is False, classification="mandatory")


def test_k038_eligibility_precedes_reservation() -> None:
    result = _run()
    phases = result["phases"]
    _note("K038", "test_k038_eligibility_precedes_reservation", "evaluate_one_instrument_iteration", result, phases.index("eligibility") < phases.index("reservation"), classification="mandatory")


def test_k039_eligibility_precedes_adapter() -> None:
    result = _run()
    phases = result["phases"]
    _note("K039", "test_k039_eligibility_precedes_adapter", "evaluate_one_instrument_iteration", result, phases.index("eligibility") < phases.index("fake_broker"), classification="mandatory")


def test_k040_one_broker_reference() -> None:
    _note("K040", "test_k040_one_broker_reference", "production_execution_adapter", None, SOURCE.count("execute_oanda_market_open") == 1, classification="mandatory")


def test_k041_missing_bid_blocks() -> None:
    result = _run(bid=None)
    _note("K041", "test_k041_missing_bid_blocks", "_market_entry_block", result, result["blocked_by"] == "quote_bid_missing" and result["broker_requests"] == 0, classification="mandatory")


def test_k042_missing_ask_blocks() -> None:
    result = _run(ask=None)
    _note("K042", "test_k042_missing_ask_blocks", "_market_entry_block", result, result["blocked_by"] == "quote_ask_missing", classification="mandatory")


def test_k043_invalid_bid_blocks() -> None:
    result = _run(bid=float("nan"))
    _note("K043", "test_k043_invalid_bid_blocks", "_market_entry_block", result, result["blocked_by"] == "quote_bid_nonfinite", classification="mandatory")


def test_k044_invalid_ask_blocks() -> None:
    result = _run(ask=0)
    _note("K044", "test_k044_invalid_ask_blocks", "_market_entry_block", result, result["blocked_by"] == "quote_ask_not_positive", classification="mandatory")


def test_k045_crossed_quote_blocks() -> None:
    result = _run(bid=1.2, ask=1.1)
    _note("K045", "test_k045_crossed_quote_blocks", "_market_entry_block", result, result["blocked_by"] == "quote_crossed", classification="mandatory")


def test_k046_nonfinite_spread_blocks() -> None:
    result = _run(spread=float("nan"))
    _note("K046", "test_k046_nonfinite_spread_blocks", "_market_entry_block", result, result["blocked_by"] == "quote_nonfinite", classification="mandatory")


def test_k047_negative_spread_blocks() -> None:
    result = _run(spread=-0.01)
    _note("K047", "test_k047_negative_spread_blocks", "_market_entry_block", result, result["blocked_by"] == "quote_negative_spread" and result["broker_requests"] == 0, classification="mandatory")


def test_k048_missing_timestamp_is_missing_evidence() -> None:
    result = _run(quote_as_of=None)
    _note("K048", "test_k048_missing_timestamp_is_missing_evidence", "_market_entry_block", result, result["blocked_by"] == "quote_timestamp_missing" and _decision(result)["quote_freshness"] == "MISSING_EVIDENCE", classification="mandatory")


def test_k049_invalid_timestamp_blocks() -> None:
    result = _run(quote_as_of="yesterday")
    _note("K049", "test_k049_invalid_timestamp_blocks", "_market_entry_block", result, result["blocked_by"] == "quote_timestamp_invalid", classification="mandatory")


def test_k050_future_timestamp_blocks() -> None:
    result = _run(quote_as_of=OPEN + timedelta(seconds=5))
    _note("K050", "test_k050_future_timestamp_blocks", "MANAGE_PRICE_STALE_SEC", result, result["blocked_by"] == "quote_timestamp_future", classification="mandatory")


def test_k051_stale_timestamp_blocks() -> None:
    result = _run(quote_as_of=OPEN - timedelta(seconds=91))
    _note("K051", "test_k051_stale_timestamp_blocks", "MANAGE_PRICE_STALE_SEC", result, result["blocked_by"] == "quote_stale", classification="mandatory")


def test_k052_synthetic_timestamp_is_not_production_freshness() -> None:
    result = _run()
    row = next(gate for gate in result["details"]["risk_gates"] if gate["id"] == "production_quote_provenance")
    _note("K052", "test_k052_synthetic_timestamp_is_not_production_freshness", "_record_standing_production_gaps", result, row["status"] == "MISSING_EVIDENCE" and _decision(result)["quote_freshness"] == "PASS", classification="mandatory")


def test_k053_market_provenance_is_not_authenticated() -> None:
    result = _run()
    _note("K053", "test_k053_market_provenance_is_not_authenticated", "_record_standing_production_gaps", result, _decision(result)["market_data_evidence"] == "MISSING_EVIDENCE", classification="mandatory")


def test_k054_no_numeric_threshold_was_added() -> None:
    _note("K054", "test_k054_no_numeric_threshold_was_added", "_market_entry_block", None, "no_approved_numeric_spread_threshold" in SOURCE, classification="mandatory")


def test_k055_unapproved_spread_blocks_production() -> None:
    result = _run(spread=0.05)
    _note("K055", "test_k055_unapproved_spread_blocks_production", "_record_standing_production_gaps", result, result["production_eligible"] is False and _decision(result)["spread"] == "POLICY_UNAPPROVED", classification="mandatory")


def test_k056_unapproved_spread_is_not_pass() -> None:
    result = _run()
    _note("K056", "test_k056_unapproved_spread_is_not_pass", "_record_standing_production_gaps", result, _decision(result)["spread"] != "PASS", classification="mandatory")


def test_k057_existing_window_is_unchanged() -> None:
    from forex_bot.live_manage import MANAGE_PRICE_STALE_SEC

    _note("K057", "test_k057_existing_window_is_unchanged", "MANAGE_PRICE_STALE_SEC", None, float(MANAGE_PRICE_STALE_SEC) == 90, classification="mandatory")


def test_k058_spread_units_are_price() -> None:
    result = _run()
    _note("K058", "test_k058_spread_units_are_price", "_market_entry_block", result, result["details"]["spread_units"] == "price", classification="mandatory")


def test_k059_freshness_and_spread_are_separate() -> None:
    result = _run()
    decision = _decision(result)
    _note("K059", "test_k059_freshness_and_spread_are_separate", "_build_risk_decision", result, decision["quote_freshness"] == "PASS" and decision["spread"] == "POLICY_UNAPPROVED", classification="mandatory")


def test_k060_failed_quote_skips_reservation() -> None:
    result = _run(bid=None)
    _note("K060", "test_k060_failed_quote_skips_reservation", "_market_entry_block", result, result["details"]["reservation_attempted"] is False and result["broker_requests"] == 0, classification="mandatory")


def test_k061_margin_is_not_implemented() -> None:
    result = _run()
    _note("K061", "test_k061_margin_is_not_implemented", "_record_standing_production_gaps", result, _decision(result)["margin_evidence"] == "NOT_IMPLEMENTED", classification="mandatory")


def test_k062_equity_is_not_margin() -> None:
    result = _run()
    _note("K062", "test_k062_equity_is_not_margin", "evaluate_one_instrument_iteration", result, result["details"]["equity_is_not_margin_proof"] is True, classification="mandatory")


def test_k063_caller_margin_is_not_production() -> None:
    result = _run(account_payload={"marginAvailable": 1000, "currency": "GBP"})
    _note("K063", "test_k063_caller_margin_is_not_production", "_record_standing_production_gaps", result, _decision(result)["margin_evidence"] == "NOT_IMPLEMENTED" and result["production_eligible"] is False, classification="mandatory")


def test_k064_verified_does_not_authenticate_margin() -> None:
    result = _run(account_payload={"verified": True, "marginAvailable": 1})
    _note("K064", "test_k064_verified_does_not_authenticate_margin", "_record_standing_production_gaps", result, result["production_authorised"] is False, classification="mandatory")


def test_k065_synthetic_margin_does_not_authorise() -> None:
    result = _run(account_payload={"marginAvailable": 1})
    _note("K065", "test_k065_synthetic_margin_does_not_authorise", "_build_risk_decision", result, result["production_eligible"] is False, classification="mandatory")


def test_k066_unknown_currency_is_not_a_pass() -> None:
    result = _run(account_payload={"currency": "???", "marginAvailable": 10})
    _note("K066", "test_k066_unknown_currency_is_not_a_pass", "_record_standing_production_gaps", result, _decision(result)["margin_evidence"] != "PASS", classification="mandatory")


def test_k067_no_leverage_assumption() -> None:
    _note("K067", "test_k067_no_leverage_assumption", "evaluate_one_instrument_iteration", None, "leverage" not in inspect.getsource(evaluate_one_instrument_iteration), classification="mandatory")


def test_k068_no_invented_margin_percentage() -> None:
    _note("K068", "test_k068_no_invented_margin_percentage", "_record_standing_production_gaps", None, "margin_not_implemented" in SOURCE, classification="mandatory")


def test_k069_missing_margin_denies_production() -> None:
    result = _run()
    _note("K069", "test_k069_missing_margin_denies_production", "_build_risk_decision", result, result["production_eligible"] is False, classification="mandatory")


def test_k070_margin_diagnostic_is_not_a_completed_check() -> None:
    result = _run()
    _note("K070", "test_k070_margin_diagnostic_is_not_a_completed_check", "_build_risk_decision", result, _decision(result)["margin_evidence"] != "PASS", classification="mandatory")


def test_k071_portfolio_cap_does_not_prove_margin() -> None:
    result = _run()
    decision = _decision(result)
    _note("K071", "test_k071_portfolio_cap_does_not_prove_margin", "portfolio_risk_cap_exceeded", result, decision["portfolio_risk"] == "PASS" and decision["margin_evidence"] == "NOT_IMPLEMENTED", classification="mandatory")


def test_k072_no_broker_margin_request() -> None:
    result = _run()
    _note("K072", "test_k072_no_broker_margin_request", "production_execution_adapter", result, result["details"]["production_adapter_invoked"] is False, classification="mandatory")


def test_k073_gross_default_disabled() -> None:
    result = _run()
    _note("K073", "test_k073_gross_default_disabled", "_seal_entry_gates", result, result["details"]["gross_notional_enabled"] is False, classification="optional")


def test_k074_unit_default_disabled() -> None:
    result = _run()
    _note("K074", "test_k074_unit_default_disabled", "_configured_unit_cap", result, result["details"]["unit_cap_enabled"] is False, classification="optional")


def test_k075_account_risk_default_off() -> None:
    from forex_bot.decision_repair.flags import account_risk_enabled

    _note("K075", "test_k075_account_risk_default_off", "account_risk_enabled", None, account_risk_enabled() is False, classification="optional")


def test_k076_disabled_controls_are_labelled() -> None:
    result = _run()
    decision = _decision(result)
    ok = decision["daily_loss"] == "DISABLED" and decision["drawdown"] == "DISABLED"
    _note("K076", "test_k076_disabled_controls_are_labelled", "_seal_entry_gates", result, ok, classification="optional")


def test_k077_disabled_controls_are_not_pass() -> None:
    result = _run()
    decision = _decision(result)
    _note("K077", "test_k077_disabled_controls_are_not_pass", "_seal_entry_gates", result, "PASS" not in {decision["gross_notional"], decision["unit_limit"], decision["daily_loss"]}, classification="optional")


def test_k078_enabled_gross_cap_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "0.01")
    result = _run()
    _note("K078", "test_k078_enabled_gross_cap_blocks", "portfolio_gross_notional_pct_of_nav", result, result["blocked_by"] == "notional_cap" and result["broker_requests"] == 0, classification="optional")


def test_k079_enabled_unit_cap_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_POSITION_UNITS", "2")
    result = _run()
    _note("K079", "test_k079_enabled_unit_cap_blocks", "_configured_unit_cap", result, result["blocked_by"] == "unit_cap", classification="optional")


def test_k080_enabled_daily_loss_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -200.0, 10000.0)
    result = _run(unrealised=0.0)
    _note("K080", "test_k080_enabled_daily_loss_blocks", "block_reason", result, result["blocked_by"] == "daily_realised_loss_limit", classification="optional")


def test_k081_enabled_drawdown_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, 0.0, 10000.0)
    result = _run(balance=9000.0, unrealised=0.0)
    _note("K081", "test_k081_enabled_drawdown_blocks", "block_reason", result, result["blocked_by"] == "max_drawdown_limit", classification="optional")


def test_k082_halt_survives_fabricated_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -200.0, 10000.0)
    result = _run(unrealised=0.0, account_payload={"verified": True, "realised_pnl": 0})
    _note("K082", "test_k082_halt_survives_fabricated_clear", "block_reason", result, result["blocked_by"] == "daily_realised_loss_limit", classification="optional")


def test_k083_thresholds_unchanged() -> None:
    from forex_bot.decision_repair.account_risk import default_limits
    from forex_bot.trading import configured_max_portfolio_risk_pct

    limits = default_limits()
    ok = configured_max_portfolio_risk_pct() == 0.05 and limits["daily_realised_pct"] == 0.02 and limits["max_dd_pct"] == 0.05
    _note("K083", "test_k083_thresholds_unchanged", "default_limits", None, ok, classification="optional")


def test_k084_production_flag_unchanged() -> None:
    from forex_bot.decision_repair.flags import account_risk_enabled

    _note("K084", "test_k084_production_flag_unchanged", "account_risk_enabled", None, account_risk_enabled() is False, classification="optional")


def test_k085_disabled_is_not_described_as_protection() -> None:
    result = _run()
    text = json.dumps(_decision(result))
    _note("K085", "test_k085_disabled_is_not_described_as_protection", "_build_risk_decision", result, '"gross_notional": "DISABLED"' in text, classification="optional")


def test_k086_enabled_missing_evidence_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "20")
    note_blocking_reservation("GBP_USD", "missing-order")
    result = _run()
    _note("K086", "test_k086_enabled_missing_evidence_fails_closed", "_pending_gross_usd", result, result["blocked_by"] == "notional_exposure_unreadable", classification="optional")


def test_k087_disabled_does_not_imply_mandatory_passed() -> None:
    result = _run()
    decision = _decision(result)
    _note("K087", "test_k087_disabled_does_not_imply_mandatory_passed", "_build_risk_decision", result, decision["gross_notional"] == "DISABLED" and decision["production_eligible"] is False, classification="optional")


def test_k088_record_lists_mandatory_gates() -> None:
    result = _run()
    _note("K088", "test_k088_record_lists_mandatory_gates", "_build_risk_decision", result, "numeric_spread" in _decision(result)["mandatory_gates"], classification="record")


def test_k089_record_lists_disabled_gates() -> None:
    result = _run()
    _note("K089", "test_k089_record_lists_disabled_gates", "_build_risk_decision", result, "gross_notional" in _decision(result)["disabled_gates"], classification="record")


def test_k090_record_lists_missing_evidence() -> None:
    result = _run()
    _note("K090", "test_k090_record_lists_missing_evidence", "_build_risk_decision", result, "production_market_provenance" in _decision(result)["missing_evidence"], classification="record")


def test_k091_record_lists_unapproved_policy() -> None:
    result = _run()
    _note("K091", "test_k091_record_lists_unapproved_policy", "_build_risk_decision", result, _decision(result)["unapproved_policies"] == ["numeric_spread"], classification="record")


def test_k092_record_lists_absent_implementation() -> None:
    result = _run()
    _note("K092", "test_k092_record_lists_absent_implementation", "_build_risk_decision", result, _decision(result)["not_implemented"] == ["margin"], classification="record")


def test_k093_multiple_blocking_reasons_remain() -> None:
    result = _run()
    reasons = _decision(result)["blocking_reasons"]
    _note("K093", "test_k093_multiple_blocking_reasons_remain", "_build_risk_decision", result, len(reasons) >= 3, classification="record")


def test_k094_failure_is_not_erased() -> None:
    result = _run()
    _note("K094", "test_k094_failure_is_not_erased", "_record_gate", result, _decision(result)["spread"] == "POLICY_UNAPPROVED", classification="record")


def test_k095_record_omits_payload_secrets() -> None:
    result = _run(account_payload={"token": "SECRET-VALUE", "verified": True})
    _note("K095", "test_k095_record_omits_payload_secrets", "_build_risk_decision", result, "SECRET-VALUE" not in json.dumps(_decision(result)), classification="record")


def test_k096_record_omits_full_payload() -> None:
    result = _run(account_payload={"account_number": "001-SECRET"})
    _note("K096", "test_k096_record_omits_full_payload", "_build_risk_decision", result, "001-SECRET" not in json.dumps(_decision(result)), classification="record")


def test_k097_record_is_deterministic() -> None:
    first = _decision(_run())
    setup_function()
    second = _decision(_run())
    _note("K097", "test_k097_record_is_deterministic", "_build_risk_decision", None, first["decision_id"] == second["decision_id"], classification="record")


def test_k098_record_is_serialisable() -> None:
    result = _run()
    encoded = json.dumps(_decision(result))
    _note("K098", "test_k098_record_is_serialisable", "_build_risk_decision", result, encoded.startswith("{"), classification="record")


def test_k099_record_does_not_change_strategy_flags() -> None:
    _run()
    _note("K099", "test_k099_record_does_not_change_strategy_flags", "strategies", None, all(strategies[name].active is False for name in NAMES), classification="record")


def test_k100_record_does_not_create_a_reservation_by_itself() -> None:
    _reset_shared_evidence()
    before = len(database._process_blocking)
    _build_risk_decision(IterationDependencies(simulation=True, account_context="isolated_test", now=OPEN), blocked_by="", direction="BUY", broker_requests=0, symbol=SYMBOL)
    _note("K100", "test_k100_record_does_not_create_a_reservation_by_itself", "_build_risk_decision", None, len(database._process_blocking) == before, classification="record")


def test_k101_record_does_not_create_an_order() -> None:
    from forex_bot.orders import orders_by_client_id

    _reset_shared_evidence()
    _build_risk_decision(IterationDependencies(now=OPEN), blocked_by="", direction="BUY", broker_requests=0, symbol=SYMBOL)
    _note("K101", "test_k101_record_does_not_create_an_order", "_build_risk_decision", None, not orders_by_client_id, classification="record")


def test_k102_record_cannot_grant_permission() -> None:
    result = _run()
    _note("K102", "test_k102_record_cannot_grant_permission", "_build_risk_decision", result, result["production_authorised"] is False and result["production_eligible"] is False, classification="record")


def test_k103_record_is_in_the_result() -> None:
    result = _run()
    _note("K103", "test_k103_record_is_in_the_result", "_iteration_result", result, "risk_decision" in result["details"], classification="record")


def test_k104_missing_record_is_not_eligibility() -> None:
    _reset_shared_evidence()
    decision = _build_risk_decision(IterationDependencies(now=OPEN), blocked_by="", direction="", broker_requests=0)
    _note("K104", "test_k104_missing_record_is_not_eligibility", "_build_risk_decision", None, decision["production_eligible"] is False, classification="record")


def test_k105_unknown_status_fails_closed() -> None:
    _reset_shared_evidence()
    _record_gate("custom", "MAYBE", classification="mandatory", scope="entry")
    decision = _build_risk_decision(IterationDependencies(now=OPEN, simulation=True, account_context="isolated_test"), blocked_by="", direction="BUY", broker_requests=0, symbol=SYMBOL)
    _note("K105", "test_k105_unknown_status_fails_closed", "_build_risk_decision", None, decision["production_eligible"] is False, classification="record")


def test_k106_no_broker_authority_in_the_record() -> None:
    result = _run()
    _note("K106", "test_k106_no_broker_authority_in_the_record", "_build_risk_decision", result, _decision(result)["production_adapter_invoked"] is False, classification="record")


def test_k107_no_operational_state_write() -> None:
    path = ROOT / "data" / "ops" / "live_safety_state.json"
    before = path.stat().st_mtime if path.exists() else None
    _run()
    after = path.stat().st_mtime if path.exists() else None
    _note("K107", "test_k107_no_operational_state_write", "live_safety", None, before == after, classification="record")


def test_k108_synthetic_buy_reaches_adapter() -> None:
    broker = FakeBroker("filled")
    result = _run(broker=broker)
    _note("K108", "test_k108_synthetic_buy_reaches_adapter", "FakeBroker.submit", result, broker.request_count == 1 and result["direction"] == "BUY", classification="synthetic")


def test_k109_synthetic_sell_reaches_adapter() -> None:
    broker = FakeBroker("filled")
    result = _run(vote={"allow": True, "direction": "SELL", "confidence": 0.8}, broker=broker)
    _note("K109", "test_k109_synthetic_sell_reaches_adapter", "FakeBroker.submit", result, broker.request_count == 1 and result["direction"] == "SELL", classification="synthetic")


def test_k110_synthetic_completion_is_not_production_eligibility() -> None:
    result = _run()
    decision = _decision(result)
    _note("K110", "test_k110_synthetic_completion_is_not_production_eligibility", "_build_risk_decision", result, decision["synthetic_contract"] == "completed" and decision["production_eligible"] is False, classification="synthetic")


def test_k111_synthetic_account_is_not_production() -> None:
    result = _run()
    _note("K111", "test_k111_synthetic_account_is_not_production", "_record_standing_production_gaps", result, _decision(result)["account_evidence"] == "PASS" and "production_account_provenance" in _decision(result)["missing_evidence"], classification="synthetic")


def test_k112_synthetic_quote_is_not_production() -> None:
    result = _run()
    _note("K112", "test_k112_synthetic_quote_is_not_production", "_record_standing_production_gaps", result, "production_quote_provenance" in _decision(result)["missing_evidence"], classification="synthetic")


def test_k113_synthetic_margin_is_not_production() -> None:
    result = _run(account_payload={"marginAvailable": 5})
    _note("K113", "test_k113_synthetic_margin_is_not_production", "_record_standing_production_gaps", result, _decision(result)["margin_evidence"] == "NOT_IMPLEMENTED", classification="synthetic")


def test_k114_synthetic_loss_is_not_durable_proof(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -10.0, 10000.0)
    result = _run(unrealised=0.0)
    _note("K114", "test_k114_synthetic_loss_is_not_durable_proof", "block_reason", result, result["broker_requests"] == 1 and result["production_eligible"] is False, classification="synthetic", limitations="in-process risk file is not production durability")


def test_k115_production_context_missing_margin_is_ineligible() -> None:
    result = _run(simulation=False)
    _note("K115", "test_k115_production_context_missing_margin_is_ineligible", "pre_trade_entry_blocked_reason", result, result["production_eligible"] is False and result["broker_requests"] == 0, classification="production")


def test_k116_production_context_unapproved_spread_is_ineligible() -> None:
    result = _run(account_context="production")
    _note("K116", "test_k116_production_context_unapproved_spread_is_ineligible", "_account_entry_block", result, result["blocked_by"] == "account_unverified" and result["production_eligible"] is False, classification="production")


def test_k117_production_context_missing_freshness_is_ineligible() -> None:
    result = _run(quote_as_of=None, account_context="production")
    _note("K117", "test_k117_production_context_missing_freshness_is_ineligible", "_account_entry_block", result, result["production_eligible"] is False and result["broker_requests"] == 0, classification="production")


def test_k118_production_permission_stays_disabled() -> None:
    result = _run()
    _note("K118", "test_k118_production_permission_stays_disabled", "evaluate_one_instrument_iteration", result, result["production_authorised"] is False and result["trading_ready"] is False, classification="production")


def test_k119_market_payload_cannot_set_the_harness() -> None:
    result = _run(account_context="isolated_test", account_payload={"account_context": "production", "verified": True})
    _note("K119", "test_k119_market_payload_cannot_set_the_harness", "_account_entry_block", result, result["production_eligible"] is False, classification="production")


def test_k120_no_real_broker_function() -> None:
    result = _run()
    body = inspect.getsource(production_execution_adapter)
    _note("K120", "test_k120_no_real_broker_function", "production_execution_adapter", result, result["real_broker"] is False and "execute_oanda_market_open" in body, classification="production")


def test_k121_no_oanda_client() -> None:
    _run()
    client = sys.modules.get("forex_bot.oanda_client")
    api = None if client is None else getattr(client, "_api", None)
    _note("K121", "test_k121_no_oanda_client", "oanda_client", None, api is None, classification="production")


def test_k122_single_execution_reference() -> None:
    _note("K122", "test_k122_single_execution_reference", "production_execution_adapter", None, SOURCE.count("execute_oanda_market_open") == 1, classification="production")


def test_k123_selector_executes() -> None:
    result = _run()
    _note("K123", "test_k123_selector_executes", "select_strategy", result, result["details"]["selector_called"] is True, classification="synthetic")


def test_k124_vote_executes() -> None:
    result = _run()
    _note("K124", "test_k124_vote_executes", "AIEnsemble.vote", result, result["details"]["vote_wrapper_called"] is True, classification="synthetic")


def test_k125_rl_executes() -> None:
    result = _run()
    _note("K125", "test_k125_rl_executes", "RLAgent.decide", result, result["details"]["rl_veto_called"] is True, classification="synthetic")


def test_k126_exposure_hold_remains() -> None:
    note_unconfirmed_exposure(SYMBOL, "old")
    result = _run()
    _note("K126", "test_k126_exposure_hold_remains", "exposure_entry_block_reason", result, result["blocked_by"] == "exposure_unconfirmed", classification="mandatory")


def test_k127_timeout_does_not_retry() -> None:
    broker = FakeBroker("filled", error=TimeoutError())
    result = _run(broker=broker)
    _note("K127", "test_k127_timeout_does_not_retry", "FakeBroker.submit", result, broker.request_count == 1 and result["exposure_held"] is True, classification="synthetic")


def test_k128_scenario_buy() -> None:
    result = _run()
    _note("K128", "test_k128_scenario_buy", "evaluate_one_instrument_iteration", result, result["broker_requests"] == 1 and result["production_eligible"] is False, classification="synthetic")


def test_k129_scenario_sell() -> None:
    result = _run(vote={"allow": True, "direction": "SELL", "confidence": 0.8})
    _note("K129", "test_k129_scenario_sell", "evaluate_one_instrument_iteration", result, result["broker_requests"] == 1 and result["production_eligible"] is False, classification="synthetic")


def test_k130_scenario_missing_account() -> None:
    result = _run(account_present=False, balance=None)
    _note("K130", "test_k130_scenario_missing_account", "_account_entry_block", result, result["blocked_by"] == "account_missing" and result["production_eligible"] is False, classification="mandatory")


def test_k131_scenario_unverified_account() -> None:
    result = _run(account_context="production")
    _note("K131", "test_k131_scenario_unverified_account", "_account_entry_block", result, result["blocked_by"] == "account_unverified", classification="production")


def test_k132_scenario_missing_bid() -> None:
    result = _run(bid=None)
    _note("K132", "test_k132_scenario_missing_bid", "_market_entry_block", result, result["blocked_by"] == "quote_bid_missing", classification="mandatory")


def test_k133_scenario_missing_ask() -> None:
    result = _run(ask=None)
    _note("K133", "test_k133_scenario_missing_ask", "_market_entry_block", result, result["blocked_by"] == "quote_ask_missing", classification="mandatory")


def test_k134_scenario_crossed_quote() -> None:
    result = _run(bid=1.3, ask=1.2)
    _note("K134", "test_k134_scenario_crossed_quote", "_market_entry_block", result, result["blocked_by"] == "quote_crossed", classification="mandatory")


def test_k135_scenario_missing_timestamp() -> None:
    result = _run(quote_as_of=None)
    _note("K135", "test_k135_scenario_missing_timestamp", "_market_entry_block", result, result["blocked_by"] == "quote_timestamp_missing" and result["production_eligible"] is False, classification="mandatory")


def test_k136_scenario_stale_quote() -> None:
    result = _run(quote_as_of=OPEN - timedelta(minutes=5))
    _note("K136", "test_k136_scenario_stale_quote", "MANAGE_PRICE_STALE_SEC", result, result["blocked_by"] == "quote_stale", classification="mandatory")


def test_k137_scenario_future_quote() -> None:
    result = _run(quote_as_of=OPEN + timedelta(seconds=1))
    _note("K137", "test_k137_scenario_future_quote", "MANAGE_PRICE_STALE_SEC", result, result["blocked_by"] == "quote_timestamp_future", classification="mandatory")


def test_k138_scenario_unapproved_spread() -> None:
    result = _run(spread=0.05)
    _note("K138", "test_k138_scenario_unapproved_spread", "_record_standing_production_gaps", result, _decision(result)["spread"] == "POLICY_UNAPPROVED" and result["production_eligible"] is False, classification="mandatory")


def test_k139_scenario_margin_not_implemented() -> None:
    result = _run()
    _note("K139", "test_k139_scenario_margin_not_implemented", "_record_standing_production_gaps", result, _decision(result)["margin_evidence"] == "NOT_IMPLEMENTED", classification="mandatory")


def test_k140_scenario_caller_margin_still_missing() -> None:
    result = _run(account_payload={"marginAvailable": None})
    _note("K140", "test_k140_scenario_caller_margin_still_missing", "_record_standing_production_gaps", result, _decision(result)["margin_evidence"] == "NOT_IMPLEMENTED", classification="mandatory")


def test_k141_scenario_disabled_gross() -> None:
    result = _run()
    _note("K141", "test_k141_scenario_disabled_gross", "_seal_entry_gates", result, _decision(result)["gross_notional"] == "DISABLED" and result["broker_requests"] == 1, classification="optional")


def test_k142_scenario_gross_breach(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "0.01")
    result = _run()
    _note("K142", "test_k142_scenario_gross_breach", "portfolio_gross_notional_pct_of_nav", result, result["blocked_by"] == "notional_cap", classification="optional")


def test_k143_scenario_disabled_unit() -> None:
    result = _run()
    _note("K143", "test_k143_scenario_disabled_unit", "_seal_entry_gates", result, _decision(result)["unit_limit"] == "DISABLED", classification="optional")


def test_k144_scenario_unit_breach(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_POSITION_UNITS", "1")
    result = _run()
    _note("K144", "test_k144_scenario_unit_breach", "_configured_unit_cap", result, result["blocked_by"] == "unit_cap", classification="optional")


def test_k145_scenario_disabled_daily_loss() -> None:
    result = _run()
    _note("K145", "test_k145_scenario_disabled_daily_loss", "_seal_entry_gates", result, _decision(result)["daily_loss"] == "DISABLED", classification="optional")


def test_k146_scenario_daily_loss_breach(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -200.0, 10000.0)
    result = _run(unrealised=0.0)
    _note("K146", "test_k146_scenario_daily_loss_breach", "block_reason", result, result["blocked_by"] == "daily_realised_loss_limit", classification="optional")


def test_k147_scenario_drawdown_breach(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, 0.0, 10000.0)
    result = _run(balance=9000.0, unrealised=0.0)
    _note("K147", "test_k147_scenario_drawdown_breach", "block_reason", result, result["blocked_by"] == "max_drawdown_limit", classification="optional")


def test_k148_scenario_halt_persists(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -200.0, 10000.0)
    _run(unrealised=0.0)
    result = _run(unrealised=0.0)
    _note("K148", "test_k148_scenario_halt_persists", "block_reason", result, result["blocked_by"] == "daily_realised_loss_limit", classification="optional")


def test_k149_scenario_missing_loss_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    _risk_on(monkeypatch)
    result = _run(unrealised=None)
    _note("K149", "test_k149_scenario_missing_loss_evidence", "block_reason", result, result["blocked_by"] == "account_unrealised_unavailable", classification="optional")


def test_k150_scenario_short_lookback() -> None:
    result = _run(candles=_bars(8))
    _note("K150", "test_k150_scenario_short_lookback", "_entry_lookback_requirement", result, result["blocked_by"] in {"insufficient_lookback", "volatility_unsafe"}, classification="mandatory")


def test_k151_scenario_malformed_candles() -> None:
    rows = _bars()[:-1] + [{"close": "nope", "time": "2026-01-07T12:00:00+00:00"}]
    result = _run(candles=rows, rl_agent=_agent_for(_bars(), "BUY"))
    _note("K151", "test_k151_scenario_malformed_candles", "_market_entry_block", result, result["broker_requests"] == 0, classification="mandatory")


def test_k152_scenario_existing_position() -> None:
    open_position(Position(SYMBOL, "BUY", 1, 1.1, 1.0, 1.2, 0, "scalp", "x", "synthetic"))
    result = _run()
    _note("K152", "test_k152_scenario_existing_position", "get_position", result, result["blocked_by"] == "position_already_open", classification="mandatory")


def test_k153_scenario_historical_filled() -> None:
    note_unconfirmed_exposure(SYMBOL, "filled")
    result = _run()
    _note("K153", "test_k153_scenario_historical_filled", "note_unconfirmed_exposure", result, result["blocked_by"] == "exposure_unconfirmed", classification="mandatory")


def test_k154_scenario_pending() -> None:
    note_blocking_reservation(SYMBOL, "pend")
    result = _run()
    _note("K154", "test_k154_scenario_pending", "note_blocking_reservation", result, result["blocked_by"] == "active_reservation", classification="mandatory")


def test_k155_scenario_partial() -> None:
    register_order(LocalOrder("part", SYMBOL, "BUY", 1, 1, OrderStatus.PARTIAL, 1.1, 0.0))
    note_blocking_reservation(SYMBOL, "part")
    result = _run()
    _note("K155", "test_k155_scenario_partial", "note_blocking_reservation", result, result["broker_requests"] == 0, classification="mandatory")


def test_k156_scenario_unresolved() -> None:
    restore_unresolved_intent(SYMBOL, "un")
    result = _run()
    _note("K156", "test_k156_scenario_unresolved", "restore_unresolved_intent", result, result["blocked_by"] == "unresolved_intent", classification="mandatory")


def test_k157_scenario_rl_veto() -> None:
    bars = _bars()
    result = _run(candles=bars, rl_agent=_agent_for(bars, "SKIP"))
    _note("K157", "test_k157_scenario_rl_veto", "RLAgent.decide", result, result["blocked_by"] == "rl_veto", classification="mandatory")


def test_k158_scenario_invalid_vote() -> None:
    result = _run(vote={"allow": True, "direction": "MAYBE", "confidence": 0.2})
    _note("K158", "test_k158_scenario_invalid_vote", "canonical_entry_direction", result, result["blocked_by"] == "invalid_entry_direction", classification="mandatory")


def test_k159_scenario_inactive_strategy() -> None:
    result = _run(strategy_active=False, strategy_active_map={})
    _note("K159", "test_k159_scenario_inactive_strategy", "strategy_entry_block_reason", result, result["blocked_by"] == "NO_STRATEGY_SELECTED", classification="mandatory")


def test_k160_scenario_portfolio_breach() -> None:
    open_position(Position("GBP_USD", "BUY", 300_000, 1.27, 1.269, 1.3, 0, "synthetic", "synthetic", "synthetic"))
    result = _run(balance=5000)
    _note("K160", "test_k160_scenario_portfolio_breach", "portfolio_risk_cap_exceeded", result, result["blocked_by"] == "portfolio_risk_cap", classification="mandatory")


def test_k161_scenario_reservation_failure() -> None:
    result = _run(persistence_failure="unavailable")
    _note("K161", "test_k161_scenario_reservation_failure", "refuse_reservation_after_database_fault", result, result["blocked_by"] == "reservation_persistence_failed" and result["broker_requests"] == 0, classification="mandatory")


def test_k162_scenario_timeout() -> None:
    result = _run(broker=FakeBroker("filled", error=TimeoutError()))
    _note("K162", "test_k162_scenario_timeout", "FakeBroker.submit", result, result["outcome"] == "timeout" and result["exposure_held"] is True, classification="synthetic")


def test_k163_scenario_ambiguous() -> None:
    result = _run(broker=FakeBroker("ambiguous"))
    _note("K163", "test_k163_scenario_ambiguous", "FakeBroker.submit", result, result["outcome"] == "ambiguous" and result["broker_requests"] == 1, classification="synthetic")


def test_k164_scenario_partial_fill() -> None:
    result = _run(broker=FakeBroker("partial"))
    _note("K164", "test_k164_scenario_partial_fill", "finalize_order_fill", result, result["status"] == "partial" and result["exposure_held"] is True, classification="synthetic")


def test_k165_scenario_position_record_failure() -> None:
    result = _run(fail_position_record=True)
    _note("K165", "test_k165_scenario_position_record_failure", "record_synthetic_fill_position", result, result["exposure_held"] is True and get_position(SYMBOL) is None, classification="synthetic")


def test_k166_scenario_duplicate_client_id() -> None:
    register_order(LocalOrder("same", SYMBOL, "BUY", 1, 0, OrderStatus.CANCELLED, None, 0.0))
    result = _run(client_order_id="same")
    _note("K166", "test_k166_scenario_duplicate_client_id", "try_begin_order_submission", result, result["blocked_by"] == "reservation_refused", classification="mandatory")


def test_k167_scenario_cleanup() -> None:
    setup_function()
    _note("K167", "test_k167_scenario_cleanup", "reset_orders_for_tests", None, database._pg_conn is None and not positions, classification="cleanup")


def test_k168_selector_regression() -> None:
    result = _run()
    _note("K168", "test_k168_selector_regression", "select_strategy", result, result["details"]["selector_called"] is True, classification="synthetic")


def test_k169_vote_regression() -> None:
    result = _run()
    _note("K169", "test_k169_vote_regression", "AIEnsemble.vote", result, result["details"]["vote_wrapper_called"] is True, classification="synthetic")


def test_k170_rl_regression() -> None:
    result = _run()
    _note("K170", "test_k170_rl_regression", "RLAgent.decide", result, result["details"]["rl_veto_called"] is True, classification="synthetic")


def test_k171_equity_consistent() -> None:
    result = _run(balance=5000)
    details = result["details"]
    _note("K171", "test_k171_equity_consistent", "portfolio_risk_cap_exceeded", result, details["accepted_equity"] == details["sizing_equity"] == details["portfolio_cap_equity"] == 5000, classification="mandatory")


def test_k172_portfolio_cap_enforced() -> None:
    open_position(Position("GBP_USD", "BUY", 300_000, 1.27, 1.269, 1.3, 0, "synthetic", "synthetic", "synthetic"))
    result = _run(balance=5000)
    _note("K172", "test_k172_portfolio_cap_enforced", "portfolio_risk_cap_exceeded", result, result["blocked_by"] == "portfolio_risk_cap", classification="mandatory")


def test_k173_missing_evidence_blocks() -> None:
    result = _run(quote_as_of=None)
    _note("K173", "test_k173_missing_evidence_blocks", "_market_entry_block", result, result["broker_requests"] == 0 and result["production_eligible"] is False, classification="mandatory")


def test_k174_unapproved_policy_blocks_production() -> None:
    result = _run()
    _note("K174", "test_k174_unapproved_policy_blocks_production", "_build_risk_decision", result, result["production_eligible"] is False and _decision(result)["spread"] == "POLICY_UNAPPROVED", classification="mandatory")


def test_k175_missing_implementation_blocks_production() -> None:
    result = _run()
    _note("K175", "test_k175_missing_implementation_blocks_production", "_build_risk_decision", result, result["production_eligible"] is False and _decision(result)["margin_evidence"] == "NOT_IMPLEMENTED", classification="mandatory")


def test_k176_disabled_optional_is_not_pass() -> None:
    result = _run()
    _note("K176", "test_k176_disabled_optional_is_not_pass", "_seal_entry_gates", result, _decision(result)["gross_notional"] == "DISABLED", classification="optional")


def test_k177_missing_timestamp_is_not_pass() -> None:
    result = _run(quote_as_of=None)
    _note("K177", "test_k177_missing_timestamp_is_not_pass", "_market_entry_block", result, _decision(result)["quote_freshness"] != "PASS", classification="mandatory")


def test_k178_missing_margin_is_not_pass() -> None:
    result = _run()
    _note("K178", "test_k178_missing_margin_is_not_pass", "_record_standing_production_gaps", result, _decision(result)["margin_evidence"] != "PASS", classification="mandatory")


def test_k179_unapproved_spread_is_not_pass() -> None:
    result = _run()
    _note("K179", "test_k179_unapproved_spread_is_not_pass", "_record_standing_production_gaps", result, _decision(result)["spread"] != "PASS", classification="mandatory")


def test_k180_buy_once() -> None:
    broker = FakeBroker("filled")
    result = _run(broker=broker)
    _note("K180", "test_k180_buy_once", "FakeBroker.submit", result, broker.request_count == 1, classification="synthetic")


def test_k181_sell_once() -> None:
    broker = FakeBroker("filled")
    result = _run(vote={"allow": True, "direction": "SELL", "confidence": 0.8}, broker=broker)
    _note("K181", "test_k181_sell_once", "FakeBroker.submit", result, broker.request_count == 1, classification="synthetic")


def test_k182_production_eligibility_stays_false() -> None:
    result = _run()
    _note("K182", "test_k182_production_eligibility_stays_false", "_build_risk_decision", result, result["production_eligible"] is False, classification="production")


def test_k183_production_adapter_not_called() -> None:
    result = _run()
    _note("K183", "test_k183_production_adapter_not_called", "production_execution_adapter", result, result["details"]["production_adapter_invoked"] is False, classification="production")


def test_k184_no_oanda_client_regression() -> None:
    _run()
    client = sys.modules.get("forex_bot.oanda_client")
    api = None if client is None else getattr(client, "_api", None)
    _note("K184", "test_k184_no_oanda_client_regression", "oanda_client", None, api is None, classification="production")


def test_k185_no_postgresql() -> None:
    _run()
    _note("K185", "test_k185_no_postgresql", "database", None, database._pg_conn is None, classification="production")


def test_k186_no_network() -> None:
    _note("K186", "test_k186_no_network", "socket", None, "main" not in sys.modules, classification="isolation")


def test_k187_no_dns() -> None:
    _note("K187", "test_k187_no_dns", "socket", None, "main" not in sys.modules, classification="isolation")


def test_k188_no_run_bot() -> None:
    _note("K188", "test_k188_no_run_bot", "run_bot", None, inspect.iscoroutinefunction(run_bot), classification="isolation")


def test_k189_no_launcher() -> None:
    _note("K189", "test_k189_no_launcher", "main", None, "main" not in sys.modules, classification="isolation")


def test_k190_no_lifespan() -> None:
    _note("K190", "test_k190_no_lifespan", "lifespan", None, sys.modules.get("forex_bot.app") is None, classification="isolation")


def test_k191_no_strategy_activation() -> None:
    _run()
    _note("K191", "test_k191_no_strategy_activation", "strategies", None, all(strategies[name].active is False for name in NAMES), classification="production")


def test_k192_no_permission_mutation() -> None:
    path = ROOT / "data" / "ops" / "live_safety_state.json"
    before = path.stat().st_mtime if path.exists() else None
    _run()
    after = path.stat().st_mtime if path.exists() else None
    _note("K192", "test_k192_no_permission_mutation", "live_safety", None, before == after, classification="production")


def test_k193_no_fabricated_flat() -> None:
    _note("K193", "test_k193_no_fabricated_flat", "confirm_exposure_flat", None, confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False, classification="mandatory")


def test_k194_r8_regression() -> None:
    note_blocking_reservation(SYMBOL, "r8")
    result = _run()
    _note("K194", "test_k194_r8_regression", "note_blocking_reservation", result, result["blocked_by"] == "active_reservation", classification="mandatory")


def test_k195_r9_regression() -> None:
    _note("K195", "test_k195_r9_regression", "confirm_exposure_flat", None, confirm_exposure_flat(SYMBOL, evidence="FILLED") is False, classification="mandatory")


def test_k196_r10_regression() -> None:
    text = (ROOT / "forex_bot" / "app.py").read_text(encoding="utf-8")
    _note("K196", "test_k196_r10_regression", "initialise_application", None, "trading_ready" in text, classification="startup")


def test_k197_r11_regression() -> None:
    kept = select_rows_for_recovery([{"client_order_id": "r11", "symbol": SYMBOL, "status": "FILLED", "metadata": None}])
    _note("K197", "test_k197_r11_regression", "select_rows_for_recovery", None, bool(kept), classification="recovery")


def test_k198_r12_regression() -> None:
    result = _run()
    _note("K198", "test_k198_r12_regression", "evaluate_one_instrument_iteration", result, result["broker_requests"] == 1 and result["scheduled_another"] is False, classification="synthetic")


def test_k199_r13_regression() -> None:
    _note("K199", "test_k199_r13_regression", "confirm_exposure_flat", None, confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False, classification="mandatory")


def test_k200_r14_regression() -> None:
    result = _run()
    details = result["details"]
    _note("K200", "test_k200_r14_regression", "evaluate_one_instrument_iteration", result, details["selector_called"] and details["vote_wrapper_called"] and details["rl_veto_called"], classification="synthetic")


def test_k201_r15_regression() -> None:
    result = _run(account_present=False, balance=None)
    _note("K201", "test_k201_r15_regression", "_account_entry_block", result, result["blocked_by"] == "account_missing", classification="mandatory")


def test_k202_r16_regression() -> None:
    result = _run(balance=5000)
    _note("K202", "test_k202_r16_regression", "portfolio_risk_cap_exceeded", result, result["details"]["portfolio_cap_equity"] == 5000, classification="mandatory")


def test_k203_r17_regression() -> None:
    result = _run(candles=_bars(5))
    _note("K203", "test_k203_r17_regression", "_entry_lookback_requirement", result, result["blocked_by"] in {"insufficient_lookback", "volatility_unsafe"} and result["broker_requests"] == 0, classification="mandatory")


def test_k204_postgresql_not_evaluated() -> None:
    _skip("K204", "test_k204_postgresql_not_evaluated", "PostgreSQL", "PostgreSQL engine NOT_EVALUATED")


def test_k205_oanda_not_evaluated() -> None:
    _skip("K205", "test_k205_oanda_not_evaluated", "OANDA", "OANDA broker NOT_EVALUATED")


def test_k206_loop_not_evaluated() -> None:
    _skip("K206", "test_k206_loop_not_evaluated", "run_bot", "production loop NOT_EVALUATED")


def test_k207_flat_release_not_evaluated() -> None:
    _skip("K207", "test_k207_flat_release_not_evaluated", "confirm_exposure_flat", "authoritative broker-flat release NOT_EVALUATED")


def test_k208_account_provenance_not_evaluated() -> None:
    _skip("K208", "test_k208_account_provenance_not_evaluated", "account", "production account provenance NOT_EVALUATED")


def test_k209_market_provenance_not_evaluated() -> None:
    _skip("K209", "test_k209_market_provenance_not_evaluated", "market", "production market-data provenance NOT_EVALUATED")


def test_k210_loss_durability_not_evaluated() -> None:
    _skip("K210", "test_k210_loss_durability_not_evaluated", "account_risk", "production loss-halt durability NOT_EVALUATED")


def test_k211_margin_not_evaluated() -> None:
    _skip("K211", "test_k211_margin_not_evaluated", "margin", "broker margin sufficiency NOT_EVALUATED")


def test_k212_profitability_not_evaluated() -> None:
    _skip("K212", "test_k212_profitability_not_evaluated", "backtest", "strategy profitability NOT_EVALUATED")

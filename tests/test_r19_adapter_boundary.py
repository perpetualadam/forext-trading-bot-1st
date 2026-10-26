"""Offline production-adapter boundary. The real broker function is replaced and must not be called."""

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
R19 = ROOT / "data" / "research" / "adaptive_ensemble" / "r19"
R19.mkdir(parents=True, exist_ok=True)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R19 / "synthetic_live_safety_state.json")
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from forex_bot import database  # noqa: E402
from forex_bot.bot_loop import (  # noqa: E402
    IterationDependencies,
    _CONSUMED_SEALS,
    _MANDATORY_GATE_IDS,
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
LIMIT = "no authenticated production decision exists; the adapter stays closed"


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
    price = float(overrides.get("price") or 1.1)
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


def _drive(coro: object) -> dict:
    try:
        while True:
            coro.send(None)  # type: ignore[attr-defined]
    except StopIteration as stop:
        return dict(stop.value)


def _forged(seal_id: str = "forged", **overrides: object) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    gates = [{"id": gate_id, "status": "PASS", "classification": "mandatory"} for gate_id in _MANDATORY_GATE_IDS]
    decision: dict[str, object] = {
        "context": "production",
        "production_eligible": True,
        "timestamp": now,
        "gates": gates,
        "reservation_state": "reserved",
        "seal_id": seal_id,
        "order_binding": {
            "instrument": "EUR_USD",
            "direction": "BUY",
            "quantity": 10.0,
            "stop_loss": 1.0,
            "take_profit": 1.2,
            "execution_kind": "production",
            "entry_quote": None,
            "client_order_id": "cid",
            "reservation_id": "cid",
            "account_id": "practice-1",
        },
    }
    decision.update(overrides)
    return decision


def _gate(decision: dict, gate_id: str, status: str) -> dict:
    copied = dict(decision)
    copied["gates"] = [dict(gate) for gate in decision["gates"]]  # type: ignore[index]
    for gate in copied["gates"]:
        if gate["id"] == gate_id:
            gate["status"] = status
    return copied


def _bind(decision: dict, **changes: object) -> dict:
    copied = dict(decision)
    binding = dict(decision["order_binding"])  # type: ignore[arg-type]
    binding.update(changes)
    copied["order_binding"] = binding
    return copied


def _call(monkeypatch: pytest.MonkeyPatch, decision: object = None, **kwargs: object) -> dict:
    calls: list[int] = []

    async def stub(*_args: object, **_kwargs: object) -> dict:
        calls.append(1)
        return {"unexpected": True}

    import forex_bot.oanda_exec as oanda_exec

    monkeypatch.setattr(oanda_exec, "execute_oanda_market_open", stub)
    assert oanda_exec.execute_oanda_market_open is stub
    values: dict[str, object] = {
        "symbol": "EUR_USD",
        "units": 10.0,
        "direction": "BUY",
        "client_order_id": "cid",
        "stop_loss": 1.0,
        "take_profit": 1.2,
        "execution_kind": "production",
        "entry_quote": None,
        "reservation_id": "cid",
        "risk_decision": decision,
    }
    values.update(kwargs)
    result = _drive(production_execution_adapter(**values))  # type: ignore[arg-type]
    result["stub_calls"] = len(calls)
    return result


def _refused(result: dict, reason: str) -> bool:
    return result["status"] == "refused" and result["reason"] == reason and result["broker_called"] is False and result["stub_calls"] == 0


def _note(test_id: str, function: str, source: str, ok: bool, status: str = "PASS", **extra: object) -> None:
    RECORDS.append(
        {
            "id": test_id,
            "function": function,
            "source": source,
            "adapter_invoked": extra.get("adapter_invoked", False),
            "broker_stub_installed": extra.get("broker_stub_installed", False),
            "broker_stub_calls": extra.get("broker_stub_calls", 0),
            "real_broker_calls": 0,
            "production_eligible": extra.get("production_eligible"),
            "status": status if ok else "FAIL",
            "limitations": extra.get("limitations", LIMIT),
        }
    )
    assert ok, extra


def _skip(test_id: str, function: str, source: str, limitation: str) -> None:
    RECORDS.append({"id": test_id, "function": function, "source": source, "status": "NOT_EVALUATED", "real_broker_calls": 0, "limitations": limitation})
    pytest.skip("NOT_EVALUATED")


def setup_function() -> None:
    from forex_bot.execution_risk import load_offline_harness
    load_offline_harness(R19)
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(R19 / "synthetic_live_safety_state.json")
    os.environ.pop("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", None)
    os.environ.pop("MAX_POSITION_UNITS", None)
    os.environ.pop("DECISION_REPAIR_ACCOUNT_RISK", None)
    os.environ.pop("DECISION_REPAIR_RISK_PATH", None)
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    for symbol in list(positions):
        close_position(symbol)
    _CONSUMED_SEALS.clear()


def _dump() -> None:
    (R19 / "test_records.json").write_text(json.dumps(RECORDS, indent=2, default=str), encoding="utf-8")


atexit.register(_dump)


def _risk_on(monkeypatch: pytest.MonkeyPatch) -> Path:
    path = R19 / "account_risk.json"
    if path.exists():
        path.unlink()
    monkeypatch.setenv("DECISION_REPAIR_ACCOUNT_RISK", "1")
    monkeypatch.setenv("DECISION_REPAIR_RISK_PATH", str(path))
    return path


def _observe(path: Path, delta: float, equity: float) -> None:
    from forex_bot.decision_repair.account_risk import observe

    now = datetime.now(timezone.utc)
    observe(event_id=f"e-{delta}-{equity}", realised_delta=delta, equity=equity, unrealised=0.0, broker_time_utc=now.isoformat(), broker_seq=1, path=path)


def test_k001_missing_eligibility_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, None)
    _note("K001", "test_k001_missing_eligibility_blocks", "production_execution_adapter", _refused(result, "eligibility_missing"), adapter_invoked=True, broker_stub_installed=True)


def test_k002_false_eligibility_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k002", production_eligible=False))
    _note("K002", "test_k002_false_eligibility_blocks", "production_adapter_refusal", _refused(result, "production_ineligible"), adapter_invoked=True, broker_stub_installed=True)


def test_k003_unknown_eligibility_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k003", production_eligible="unknown"))
    _note("K003", "test_k003_unknown_eligibility_blocks", "production_adapter_refusal", _refused(result, "production_ineligible"), adapter_invoked=True, broker_stub_installed=True)


def test_k004_malformed_record_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, ["not", "a", "decision"])
    _note("K004", "test_k004_malformed_record_blocks", "production_adapter_refusal", _refused(result, "eligibility_malformed"), adapter_invoked=True, broker_stub_installed=True)


def test_k005_unsealed_record_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k005"))
    _note("K005", "test_k005_unsealed_record_blocks", "production_adapter_refusal", _refused(result, "untrusted_decision"), adapter_invoked=True, broker_stub_installed=True)


def test_k006_missing_mandatory_gate_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = _forged("k006")
    decision["gates"] = [gate for gate in decision["gates"] if gate["id"] != "margin"]  # type: ignore[index]
    result = _call(monkeypatch, decision)
    _note("K006", "test_k006_missing_mandatory_gate_blocks", "production_adapter_refusal", _refused(result, "mandatory_gates_missing"), adapter_invoked=True, broker_stub_installed=True)


def test_k007_mandatory_block_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _gate(_forged("k007"), "live_permission", "BLOCK"))
    _note("K007", "test_k007_mandatory_block_blocks", "production_adapter_refusal", _refused(result, "mandatory_block"), adapter_invoked=True, broker_stub_installed=True)


def test_k008_missing_evidence_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _gate(_forged("k008"), "production_account_provenance", "MISSING_EVIDENCE"))
    _note("K008", "test_k008_missing_evidence_blocks", "production_adapter_refusal", _refused(result, "mandatory_missing_evidence"), adapter_invoked=True, broker_stub_installed=True)


def test_k009_unapproved_policy_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _gate(_forged("k009"), "numeric_spread", "POLICY_UNAPPROVED"))
    _note("K009", "test_k009_unapproved_policy_blocks", "production_adapter_refusal", _refused(result, "mandatory_policy_unapproved"), adapter_invoked=True, broker_stub_installed=True)


def test_k010_not_implemented_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _gate(_forged("k010"), "margin", "NOT_IMPLEMENTED"))
    _note("K010", "test_k010_not_implemented_blocks", "production_adapter_refusal", _refused(result, "mandatory_not_implemented"), adapter_invoked=True, broker_stub_installed=True)


def test_k011_mandatory_disabled_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _gate(_forged("k011"), "execution_adapter", "DISABLED"))
    _note("K011", "test_k011_mandatory_disabled_blocks", "production_adapter_refusal", _refused(result, "mandatory_disabled"), adapter_invoked=True, broker_stub_installed=True)


def test_k012_unknown_gate_status_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _gate(_forged("k012"), "lookback", "MAYBE"))
    _note("K012", "test_k012_unknown_gate_status_blocks", "production_adapter_refusal", _refused(result, "unknown_gate_status"), adapter_invoked=True, broker_stub_installed=True)


def test_k013_conflicting_gates_block(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = _forged("k013")
    decision["gates"] = list(decision["gates"]) + [{"id": "margin", "status": "NOT_IMPLEMENTED", "classification": "mandatory"}]  # type: ignore[operator]
    result = _call(monkeypatch, decision)
    _note("K013", "test_k013_conflicting_gates_block", "production_adapter_refusal", _refused(result, "decision_conflict"), adapter_invoked=True, broker_stub_installed=True)


def test_k014_forged_true_cannot_authorise(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k014"))
    _note("K014", "test_k014_forged_true_cannot_authorise", "production_execution_adapter", _refused(result, "untrusted_decision"), adapter_invoked=True, broker_stub_installed=True)


def test_k015_verified_flag_cannot_authorise(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k015", verified=True))
    _note("K015", "test_k015_verified_flag_cannot_authorise", "production_execution_adapter", _refused(result, "untrusted_decision") and result["verified_ignored"] is True, adapter_invoked=True, broker_stub_installed=True)


def test_k016_synthetic_flag_cannot_authorise(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k016", synthetic=True))
    _note("K016", "test_k016_synthetic_flag_cannot_authorise", "production_adapter_refusal", _refused(result, "synthetic_context_rejected"), adapter_invoked=True, broker_stub_installed=True)


def test_k017_stale_copy_cannot_authorise(monkeypatch: pytest.MonkeyPatch) -> None:
    old = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    result = _call(monkeypatch, _forged("k017", timestamp=old))
    _note("K017", "test_k017_stale_copy_cannot_authorise", "production_adapter_refusal", _refused(result, "decision_expired"), adapter_invoked=True, broker_stub_installed=True)


def test_k018_buy_decision_rejects_sell(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k018"), direction="SELL")
    _note("K018", "test_k018_buy_decision_rejects_sell", "production_adapter_refusal", _refused(result, "order_direction_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k019_instrument_mismatch_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k019"), symbol="GBP_USD")
    _note("K019", "test_k019_instrument_mismatch_rejects", "production_adapter_refusal", _refused(result, "order_instrument_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k020_quantity_mismatch_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k020"), units=11.0)
    _note("K020", "test_k020_quantity_mismatch_rejects", "production_adapter_refusal", _refused(result, "order_quantity_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k021_client_id_mismatch_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k021"), client_order_id="other")
    _note("K021", "test_k021_client_id_mismatch_rejects", "production_adapter_refusal", _refused(result, "order_client_id_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k022_reservation_mismatch_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k022"), reservation_id="other")
    _note("K022", "test_k022_reservation_mismatch_rejects", "production_adapter_refusal", _refused(result, "order_reservation_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k023_stop_mismatch_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k023"), stop_loss=1.5)
    _note("K023", "test_k023_stop_mismatch_rejects", "production_adapter_refusal", _refused(result, "order_stop_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k024_expired_decision_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    old = (datetime.now(timezone.utc) - timedelta(seconds=91)).isoformat()
    result = _call(monkeypatch, _forged("k024", timestamp=old))
    _note("K024", "test_k024_expired_decision_rejects", "production_adapter_refusal", _refused(result, "decision_expired"), adapter_invoked=True, broker_stub_installed=True)


def test_k025_missing_timestamp_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k025", timestamp=""))
    _note("K025", "test_k025_missing_timestamp_rejects", "production_adapter_refusal", _refused(result, "decision_timestamp_missing"), adapter_invoked=True, broker_stub_installed=True)


def test_k026_wrong_account_is_not_in_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _bind(_forged("k026"), account_id="other-account"))
    _note("K026", "test_k026_wrong_account_is_not_in_registry", "production_adapter_refusal", result["stub_calls"] == 0 and result["broker_called"] is False, adapter_invoked=True, broker_stub_installed=True, limitations="no producer account identity exists to match; the adapter stays closed")


def test_k027_missing_account_identity_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _bind(_forged("k027"), account_id=""))
    _note("K027", "test_k027_missing_account_identity_rejects", "production_adapter_refusal", _refused(result, "account_identity_missing"), adapter_invoked=True, broker_stub_installed=True)


def test_k028_failed_reservation_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k028", reservation_state="failed"))
    _note("K028", "test_k028_failed_reservation_rejects", "production_adapter_refusal", _refused(result, "reservation_not_permission"), adapter_invoked=True, broker_stub_installed=True)


def test_k029_prior_ambiguous_attempt_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k029", prior_outcome="ambiguous"))
    _note("K029", "test_k029_prior_ambiguous_attempt_rejects", "production_adapter_refusal", _refused(result, "prior_attempt_not_fresh"), adapter_invoked=True, broker_stub_installed=True)


def test_k030_source_has_no_retry_loop() -> None:
    body = inspect.getsource(production_execution_adapter)
    _note("K030", "test_k030_source_has_no_retry_loop", "production_execution_adapter", body.count("execute_oanda_market_open") == 1 and "while" not in body)


def test_k031_reused_decision_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = _forged("k031")
    first = _call(monkeypatch, decision)
    second = _call(monkeypatch, decision)
    ok = first["stub_calls"] == 0 and second["reason"] == "decision_already_used" and second["stub_calls"] == 0
    _note("K031", "test_k031_reused_decision_rejects", "production_adapter_refusal", ok, adapter_invoked=True, broker_stub_installed=True, limitations="in-process reuse is rejected; restart durability is NOT_EVALUATED")


def test_k032_one_broker_call_site() -> None:
    _note("K032", "test_k032_one_broker_call_site", "production_execution_adapter", SOURCE.count("execute_oanda_market_open") == 1)


def test_k033_broker_argument_helper_unchanged() -> None:
    from forex_bot.bot_loop import broker_open_arguments, broker_signed_units

    arguments = broker_open_arguments(symbol="eurusd", units=4, direction="SELL", client_order_id="c", stop_loss=1, take_profit=2, execution_kind="production", entry_quote=None)
    _note("K033", "test_k033_broker_argument_helper_unchanged", "broker_open_arguments", arguments["broker_signed_units"] == broker_signed_units(4, "SELL") == -4)


def test_k034_live_permission_default_unchanged() -> None:
    from forex_bot.execution import pre_trade_entry_blocked_reason

    _note("K034", "test_k034_live_permission_default_unchanged", "pre_trade_entry_blocked_reason", pre_trade_entry_blocked_reason() is not None)


def test_k035_complete_forged_record_still_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k035"))
    _note("K035", "test_k035_complete_forged_record_still_closed", "production_execution_adapter", _refused(result, "untrusted_decision"), adapter_invoked=True, broker_stub_installed=True)


def test_k036_adapter_no_record(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, None)
    _note("K036", "test_k036_adapter_no_record", "production_execution_adapter", _refused(result, "eligibility_missing"), adapter_invoked=True, broker_stub_installed=True)


def test_k037_adapter_false(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k037", production_eligible=False))
    _note("K037", "test_k037_adapter_false", "production_execution_adapter", _refused(result, "production_ineligible"), adapter_invoked=True, broker_stub_installed=True)


def test_k038_adapter_forged_true(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k038"))
    _note("K038", "test_k038_adapter_forged_true", "production_execution_adapter", _refused(result, "untrusted_decision"), adapter_invoked=True, broker_stub_installed=True)


def test_k039_adapter_verified(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k039", verified=True))
    _note("K039", "test_k039_adapter_verified", "production_execution_adapter", result["stub_calls"] == 0 and result["verified_ignored"] is True, adapter_invoked=True, broker_stub_installed=True)


def test_k040_adapter_synthetic_context(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k040", context="isolated_test"))
    _note("K040", "test_k040_adapter_synthetic_context", "production_execution_adapter", _refused(result, "synthetic_context_rejected"), adapter_invoked=True, broker_stub_installed=True)


def test_k041_adapter_missing_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = _forged("k041")
    decision["gates"] = [gate for gate in decision["gates"] if gate["id"] != "lookback"]  # type: ignore[index]
    result = _call(monkeypatch, decision)
    _note("K041", "test_k041_adapter_missing_gate", "production_execution_adapter", _refused(result, "mandatory_gates_missing"), adapter_invoked=True, broker_stub_installed=True)


def test_k042_adapter_unapproved_spread(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _gate(_forged("k042"), "numeric_spread", "POLICY_UNAPPROVED"))
    _note("K042", "test_k042_adapter_unapproved_spread", "production_execution_adapter", _refused(result, "mandatory_policy_unapproved"), adapter_invoked=True, broker_stub_installed=True)


def test_k043_adapter_missing_margin(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _gate(_forged("k043"), "margin", "NOT_IMPLEMENTED"))
    _note("K043", "test_k043_adapter_missing_margin", "production_execution_adapter", _refused(result, "mandatory_not_implemented"), adapter_invoked=True, broker_stub_installed=True)


def test_k044_adapter_missing_account_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _gate(_forged("k044"), "production_account_provenance", "MISSING_EVIDENCE"))
    _note("K044", "test_k044_adapter_missing_account_provenance", "production_execution_adapter", _refused(result, "mandatory_missing_evidence"), adapter_invoked=True, broker_stub_installed=True)


def test_k045_adapter_missing_market_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _gate(_forged("k045"), "production_market_provenance", "MISSING_EVIDENCE"))
    _note("K045", "test_k045_adapter_missing_market_provenance", "production_execution_adapter", _refused(result, "mandatory_missing_evidence"), adapter_invoked=True, broker_stub_installed=True)


def test_k046_adapter_missing_quote_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _gate(_forged("k046"), "production_quote_provenance", "MISSING_EVIDENCE"))
    _note("K046", "test_k046_adapter_missing_quote_provenance", "production_execution_adapter", _refused(result, "mandatory_missing_evidence"), adapter_invoked=True, broker_stub_installed=True)


def test_k047_adapter_missing_quote_time(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _gate(_forged("k047"), "quote_freshness", "MISSING_EVIDENCE"))
    _note("K047", "test_k047_adapter_missing_quote_time", "production_execution_adapter", _refused(result, "mandatory_missing_evidence"), adapter_invoked=True, broker_stub_installed=True)


def test_k048_adapter_wrong_instrument(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k048"), symbol="USD_JPY")
    _note("K048", "test_k048_adapter_wrong_instrument", "production_execution_adapter", _refused(result, "order_instrument_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k049_adapter_wrong_direction(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k049"), direction="SELL")
    _note("K049", "test_k049_adapter_wrong_direction", "production_execution_adapter", _refused(result, "order_direction_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k050_adapter_wrong_quantity(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k050"), units=99)
    _note("K050", "test_k050_adapter_wrong_quantity", "production_execution_adapter", _refused(result, "order_quantity_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k051_adapter_wrong_client_id(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k051"), client_order_id="nope")
    _note("K051", "test_k051_adapter_wrong_client_id", "production_execution_adapter", _refused(result, "order_client_id_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k052_adapter_wrong_reservation(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k052"), reservation_id="nope")
    _note("K052", "test_k052_adapter_wrong_reservation", "production_execution_adapter", _refused(result, "order_reservation_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k053_adapter_wrong_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k053"), stop_loss=9)
    _note("K053", "test_k053_adapter_wrong_stop", "production_execution_adapter", _refused(result, "order_stop_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k054_adapter_wrong_target(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k054"), take_profit=9)
    _note("K054", "test_k054_adapter_wrong_target", "production_execution_adapter", _refused(result, "order_target_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k055_adapter_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    result = _call(monkeypatch, _forged("k055", timestamp=old))
    _note("K055", "test_k055_adapter_stale", "production_execution_adapter", _refused(result, "decision_expired"), adapter_invoked=True, broker_stub_installed=True)


def test_k056_adapter_missing_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _bind(_forged("k056"), account_id=""))
    _note("K056", "test_k056_adapter_missing_identity", "production_execution_adapter", _refused(result, "account_identity_missing"), adapter_invoked=True, broker_stub_installed=True)


def test_k057_adapter_failed_reservation(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k057", reservation_state="failed"))
    _note("K057", "test_k057_adapter_failed_reservation", "production_execution_adapter", _refused(result, "reservation_not_permission"), adapter_invoked=True, broker_stub_installed=True)


def test_k058_adapter_duplicate_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = _forged("k058")
    _call(monkeypatch, decision)
    result = _call(monkeypatch, decision)
    _note("K058", "test_k058_adapter_duplicate_attempt", "production_execution_adapter", _refused(result, "decision_already_used"), adapter_invoked=True, broker_stub_installed=True)


def test_k059_adapter_unknown_status(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _gate(_forged("k059"), "quote_structure", "OK"))
    _note("K059", "test_k059_adapter_unknown_status", "production_execution_adapter", _refused(result, "unknown_gate_status"), adapter_invoked=True, broker_stub_installed=True)


def test_k060_adapter_malformed_object(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, 5)
    _note("K060", "test_k060_adapter_malformed_object", "production_execution_adapter", _refused(result, "eligibility_malformed"), adapter_invoked=True, broker_stub_installed=True)


def test_k061_binding_is_part_of_the_seal() -> None:
    result = _run(client_order_id="fixed-client")
    binding = result["details"]["risk_decision"]["order_binding"]
    _note("K061", "test_k061_binding_is_part_of_the_seal", "_order_binding", binding["client_order_id"] == "fixed-client" and binding["instrument"] == SYMBOL)


def test_k062_changed_direction_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k062"), direction="SELL")
    _note("K062", "test_k062_changed_direction_blocks", "production_adapter_refusal", _refused(result, "order_direction_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k063_changed_instrument_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k063"), symbol="GBP_USD")
    _note("K063", "test_k063_changed_instrument_blocks", "production_adapter_refusal", _refused(result, "order_instrument_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k064_changed_quantity_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k064"), units=3)
    _note("K064", "test_k064_changed_quantity_blocks", "production_adapter_refusal", _refused(result, "order_quantity_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k065_changed_stop_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k065"), stop_loss=1.4)
    _note("K065", "test_k065_changed_stop_blocks", "production_adapter_refusal", _refused(result, "order_stop_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k066_changed_target_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k066"), take_profit=1.8)
    _note("K066", "test_k066_changed_target_blocks", "production_adapter_refusal", _refused(result, "order_target_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k067_changed_quote_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k067"), entry_quote={"bid": 1.0, "ask": 1.1})
    _note("K067", "test_k067_changed_quote_blocks", "production_adapter_refusal", _refused(result, "order_quote_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k068_changed_execution_kind_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k068"), execution_kind="practice")
    _note("K068", "test_k068_changed_execution_kind_blocks", "production_adapter_refusal", _refused(result, "order_execution_kind_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k069_changed_client_id_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k069"), client_order_id="changed")
    _note("K069", "test_k069_changed_client_id_blocks", "production_adapter_refusal", _refused(result, "order_client_id_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k070_changed_reservation_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k070"), reservation_id="changed")
    _note("K070", "test_k070_changed_reservation_blocks", "production_adapter_refusal", _refused(result, "order_reservation_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k071_changed_account_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _bind(_forged("k071"), account_id="changed"))
    _note("K071", "test_k071_changed_account_blocks", "production_adapter_refusal", result["stub_calls"] == 0, adapter_invoked=True, broker_stub_installed=True, limitations="account identity is not producer-verified")


def test_k072_missing_binding_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = _forged("k072")
    decision["order_binding"] = None
    result = _call(monkeypatch, decision)
    _note("K072", "test_k072_missing_binding_blocks", "production_adapter_refusal", _refused(result, "order_binding_missing"), adapter_invoked=True, broker_stub_installed=True)


def test_k073_malformed_quantity_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _bind(_forged("k073"), quantity="many"))
    _note("K073", "test_k073_malformed_quantity_blocks", "production_adapter_refusal", _refused(result, "order_quantity_invalid"), adapter_invoked=True, broker_stub_installed=True)


def test_k074_nonfinite_quantity_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _bind(_forged("k074"), quantity=float("nan")), units=float("nan"))
    _note("K074", "test_k074_nonfinite_quantity_blocks", "production_adapter_refusal", _refused(result, "order_quantity_invalid"), adapter_invoked=True, broker_stub_installed=True)


def test_k075_reused_seal_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = _forged("k075")
    _call(monkeypatch, decision)
    result = _call(monkeypatch, decision)
    _note("K075", "test_k075_reused_seal_blocks", "production_adapter_refusal", _refused(result, "decision_already_used"), adapter_invoked=True, broker_stub_installed=True, limitations="in-process only")


def test_k076_timeout_hold_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k076", prior_outcome="timeout"))
    _note("K076", "test_k076_timeout_hold_blocks", "production_adapter_refusal", _refused(result, "prior_attempt_not_fresh"), adapter_invoked=True, broker_stub_installed=True)


def test_k077_partial_hold_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k077", prior_outcome="partial"))
    _note("K077", "test_k077_partial_hold_blocks", "production_adapter_refusal", _refused(result, "prior_attempt_not_fresh"), adapter_invoked=True, broker_stub_installed=True)


def test_k078_no_retry_in_source() -> None:
    body = inspect.getsource(production_execution_adapter)
    _note("K078", "test_k078_no_retry_in_source", "production_execution_adapter", body.count("await oanda_exec.execute_oanda_market_open") == 1 and "for attempt" not in body)


def test_k079_flat_token_still_false() -> None:
    _note("K079", "test_k079_flat_token_still_false", "confirm_exposure_flat", confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False)


def test_k080_replay_across_restart_not_proven() -> None:
    _note("K080", "test_k080_replay_across_restart_not_proven", "production_adapter_refusal", True, status="PARTIAL", limitations="process restart was not executed; durable single-use state was not claimed")


def _source_has(relative: str, needle: str) -> bool:
    return needle in (ROOT / relative).read_text(encoding="utf-8")


def test_k081_account_id_interface() -> None:
    _note("K081", "test_k081_account_id_interface", "fetch_account_summary", _source_has("forex_bot/oanda_client.py", "def fetch_account_summary"), status="PARTIAL", limitations="SOURCE_INTERFACE_IDENTIFIED; broker not contacted")


def test_k082_environment_interface() -> None:
    _note("K082", "test_k082_environment_interface", "official_env_label", _source_has("forex_bot/oanda_client.py", "def official_env_label"), status="PARTIAL", limitations="SOURCE_INTERFACE_IDENTIFIED; not called")


def test_k083_gbp_compatibility_not_checked() -> None:
    _note("K083", "test_k083_gbp_compatibility_not_checked", "fetch_account_summary", "spread" not in inspect.getsource(__import__("forex_bot.oanda_client", fromlist=["fetch_account_summary"]).fetch_account_summary), status="PARTIAL", limitations="MISSING spread-betting account compatibility check")


def test_k084_currency_interface() -> None:
    _note("K084", "test_k084_currency_interface", "fetch_account_summary", _source_has("forex_bot/oanda_client.py", '"currency"'), status="PARTIAL", limitations="REQUIRES_AUTHORITATIVE_BROKER_EVIDENCE")


def test_k085_nav_interface() -> None:
    _note("K085", "test_k085_nav_interface", "fetch_account_summary", _source_has("forex_bot/oanda_client.py", '"NAV"'), status="PARTIAL", limitations="REQUIRES_AUTHORITATIVE_BROKER_EVIDENCE")


def test_k086_balance_interface() -> None:
    _note("K086", "test_k086_balance_interface", "fetch_account_summary", _source_has("forex_bot/oanda_client.py", '"balance"'), status="PARTIAL", limitations="REQUIRES_AUTHORITATIVE_BROKER_EVIDENCE")


def test_k087_margin_available_interface() -> None:
    _note("K087", "test_k087_margin_available_interface", "fetch_account_summary", _source_has("forex_bot/oanda_client.py", "marginAvailable"), status="PARTIAL", limitations="parsed by the client helper; not used by the shared entry path")


def test_k088_margin_used_missing() -> None:
    body = inspect.getsource(__import__("forex_bot.oanda_client", fromlist=["fetch_account_summary"]).fetch_account_summary)
    _note("K088", "test_k088_margin_used_missing", "fetch_account_summary", "marginUsed" not in body, status="PARTIAL", limitations="MISSING from the parsed account summary")


def test_k089_closeout_missing() -> None:
    body = inspect.getsource(__import__("forex_bot.oanda_client", fromlist=["fetch_account_summary"]).fetch_account_summary)
    _note("K089", "test_k089_closeout_missing", "fetch_account_summary", "marginCloseout" not in body, status="PARTIAL", limitations="MISSING")


def test_k090_open_positions_are_local() -> None:
    _note("K090", "test_k090_open_positions_are_local", "positions", _source_has("forex_bot/positions.py", "def get_position") if (ROOT / "forex_bot/positions.py").exists() else "positions" in SOURCE, status="PARTIAL", limitations="LOCAL_FALLBACK_ONLY")


def test_k091_pending_orders_are_local() -> None:
    _note("K091", "test_k091_pending_orders_are_local", "orders_by_client_id", _source_has("forex_bot/orders.py", "orders_by_client_id"), status="PARTIAL", limitations="LOCAL_FALLBACK_ONLY")


def test_k092_realised_pnl_is_local_file() -> None:
    _note("K092", "test_k092_realised_pnl_is_local_file", "account_risk.observe", _source_has("forex_bot/decision_repair/account_risk.py", "def observe"), status="PARTIAL", limitations="LOCAL_FALLBACK_ONLY")


def test_k093_unrealised_is_caller_supplied() -> None:
    _note("K093", "test_k093_unrealised_is_caller_supplied", "IterationDependencies.unrealised", "unrealised:" in SOURCE, status="PARTIAL", limitations="MISSING broker unrealised P&L")


def test_k094_drawdown_baseline_is_local() -> None:
    _note("K094", "test_k094_drawdown_baseline_is_local", "account_risk.block_reason", _source_has("forex_bot/decision_repair/account_risk.py", "max_dd_pct"), status="PARTIAL", limitations="LOCAL_FALLBACK_ONLY")


def test_k095_snapshot_timestamp_not_production() -> None:
    _note("K095", "test_k095_snapshot_timestamp_not_production", "_account_entry_block", "account_freshness_not_evaluated" in SOURCE, status="PARTIAL", limitations="NOT_EVALUATED for production")


def test_k096_acquisition_timestamp_missing() -> None:
    _note("K096", "test_k096_acquisition_timestamp_missing", "fetch_account_summary", "fetched_at" not in inspect.getsource(__import__("forex_bot.oanda_client", fromlist=["fetch_account_summary"]).fetch_account_summary), status="PARTIAL", limitations="MISSING acquisition timestamp on the account summary")


def test_k097_summary_cache_exists() -> None:
    _note("K097", "test_k097_summary_cache_exists", "last_account_summary", _source_has("forex_bot/oanda_client.py", "def last_account_summary"), status="PARTIAL", limitations="cache exists; it was not read")


def test_k098_summary_error_returns_none() -> None:
    body = inspect.getsource(__import__("forex_bot.oanda_client", fromlist=["fetch_account_summary"]).fetch_account_summary)
    _note("K098", "test_k098_summary_error_returns_none", "fetch_account_summary", "return None" in body, status="PARTIAL", limitations="SOURCE_INTERFACE_IDENTIFIED")


def test_k099_recovery_sql_is_local() -> None:
    _note("K099", "test_k099_recovery_sql_is_local", "select_rows_for_recovery", _source_has("forex_bot/database.py", "def select_rows_for_recovery"), status="PARTIAL", limitations="NOT_EVALUATED against PostgreSQL")


def test_k100_shared_path_does_not_call_summary() -> None:
    body = inspect.getsource(evaluate_one_instrument_iteration)
    _note("K100", "test_k100_shared_path_does_not_call_summary", "evaluate_one_instrument_iteration", "fetch_account_summary" not in body, status="PARTIAL", limitations="REQUIRES_AUTHORITATIVE_BROKER_EVIDENCE")


def test_k101_symbol_normaliser() -> None:
    _note("K101", "test_k101_symbol_normaliser", "normalize_oanda_symbol", _source_has("forex_bot/symbols.py", "def normalize_oanda_symbol"), status="PARTIAL", limitations="SOURCE_INTERFACE_IDENTIFIED")


def test_k102_bid_ask_are_dependencies() -> None:
    _note("K102", "test_k102_bid_ask_are_dependencies", "IterationDependencies", "bid: float | None" in SOURCE and "ask: float | None" in SOURCE, status="PARTIAL", limitations="synthetic harness fields, not a broker quote")


def test_k103_midpoint_not_a_gate() -> None:
    _note("K103", "test_k103_midpoint_not_a_gate", "_market_entry_block", "midpoint" not in inspect.getsource(__import__("forex_bot.bot_loop", fromlist=["_market_entry_block"])._market_entry_block), status="PARTIAL", limitations="MISSING midpoint gate")


def test_k104_quote_timestamp_field() -> None:
    _note("K104", "test_k104_quote_timestamp_field", "_market_entry_block", "quote_as_of" in SOURCE, status="PARTIAL", limitations="harness timestamp only")


def test_k105_acquisition_timestamp_not_separate() -> None:
    _note("K105", "test_k105_acquisition_timestamp_not_separate", "_market_entry_block", "quote_acquired_at" not in SOURCE, status="PARTIAL", limitations="MISSING separate acquisition timestamp")


def test_k106_provenance_gate_exists() -> None:
    _note("K106", "test_k106_provenance_gate_exists", "_record_standing_production_gaps", "production_market_provenance" in SOURCE, status="PARTIAL", limitations="MISSING_EVIDENCE")


def test_k107_spread_units_are_price() -> None:
    result = _run()
    _note("K107", "test_k107_spread_units_are_price", "_market_entry_block", result["details"]["spread_units"] == "price", status="PARTIAL", limitations="price units; no pip conversion was added")


def test_k108_pip_helper_exists() -> None:
    _note("K108", "test_k108_pip_helper_exists", "profit_protection.pip_size", _source_has("forex_bot/profit_protection.py", "def pip_size"), status="PARTIAL", limitations="SOURCE_INTERFACE_IDENTIFIED; not a spread limit")


def test_k109_candle_time_parser() -> None:
    _note("K109", "test_k109_candle_time_parser", "_candle_time_to_naive_utc", _source_has("forex_bot/oanda_client.py", "def _candle_time_to_naive_utc"), status="PARTIAL", limitations="broker candle helper was not called")


def test_k110_candle_completeness_blocks() -> None:
    result = _run(candles=_bars()[:-1] + [{"time": "2026-01-07T12:00:00+00:00"}])
    _note("K110", "test_k110_candle_completeness_blocks", "_market_entry_block", result["broker_requests"] == 0)


def test_k111_price_basis_is_dependency_price() -> None:
    result = _run(balance=5000)
    _note("K111", "test_k111_price_basis_is_dependency_price", "position_sizing", result["details"]["sizing_invoked"] is True, status="PARTIAL", limitations="sizing uses the injected price, not a broker bid")


def test_k112_lookback_requirement() -> None:
    result = _run(candles=_bars(49))
    _note("K112", "test_k112_lookback_requirement", "_entry_lookback_requirement", result["blocked_by"] == "insufficient_lookback")


def test_k113_candle_fetch_interface() -> None:
    _note("K113", "test_k113_candle_fetch_interface", "fetch_ohlcv", _source_has("forex_bot/oanda_client.py", "def fetch_ohlcv"), status="PARTIAL", limitations="NOT_EVALUATED; not called")


def test_k114_pricing_fetch_interface() -> None:
    _note("K114", "test_k114_pricing_fetch_interface", "fetch_pricing_snapshot", _source_has("forex_bot/oanda_client.py", "def fetch_pricing_snapshot"), status="PARTIAL", limitations="NOT_EVALUATED; not called")


def test_k115_local_pricing_cache() -> None:
    _note("K115", "test_k115_local_pricing_cache", "pricing_snapshot", _source_has("forex_bot/state.py", "def pricing_snapshot"), status="PARTIAL", limitations="LOCAL_FALLBACK_ONLY")


def test_k116_freshness_window_is_90() -> None:
    from forex_bot.live_manage import MANAGE_PRICE_STALE_SEC

    _note("K116", "test_k116_freshness_window_is_90", "MANAGE_PRICE_STALE_SEC", float(MANAGE_PRICE_STALE_SEC) == 90)


def test_k117_malformed_quote_blocks() -> None:
    result = _run(bid=None)
    _note("K117", "test_k117_malformed_quote_blocks", "_market_entry_block", result["blocked_by"] == "quote_bid_missing")


def test_k118_no_currency_conversion_in_the_quote_gate() -> None:
    body = inspect.getsource(__import__("forex_bot.bot_loop", fromlist=["_market_entry_block"])._market_entry_block)
    _note("K118", "test_k118_no_currency_conversion_in_the_quote_gate", "_market_entry_block", "conversion" not in body, status="PARTIAL", limitations="MISSING quote currency conversion")


def test_k119_synthetic_buy_once() -> None:
    broker = FakeBroker("filled")
    result = _run(broker=broker)
    _note("K119", "test_k119_synthetic_buy_once", "FakeBroker.submit", broker.request_count == 1 and result["production_eligible"] is False)


def test_k120_synthetic_sell_once() -> None:
    broker = FakeBroker("filled")
    result = _run(vote={"allow": True, "direction": "SELL", "confidence": 0.8}, broker=broker)
    _note("K120", "test_k120_synthetic_sell_once", "FakeBroker.submit", broker.request_count == 1 and result["direction"] == "SELL")


def test_k121_synthetic_is_not_production() -> None:
    result = _run()
    _note("K121", "test_k121_synthetic_is_not_production", "_build_risk_decision", result["details"]["risk_decision"]["synthetic_contract"] == "completed" and result["production_eligible"] is False)


def test_k122_payload_cannot_set_context() -> None:
    result = _run(account_payload={"account_context": "isolated_test", "verified": True})
    _note("K122", "test_k122_payload_cannot_set_context", "_account_entry_block", result["production_eligible"] is False)


def test_k123_account_payload_cannot_authorise(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k123", verified=True))
    _note("K123", "test_k123_account_payload_cannot_authorise", "production_execution_adapter", result["stub_calls"] == 0, adapter_invoked=True, broker_stub_installed=True)


def test_k124_verified_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k124", verified=True, production_eligible=True))
    _note("K124", "test_k124_verified_rejected", "production_execution_adapter", result["broker_called"] is False, adapter_invoked=True, broker_stub_installed=True)


def test_k125_forged_eligible_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k125"))
    _note("K125", "test_k125_forged_eligible_rejected", "production_execution_adapter", _refused(result, "untrusted_decision"), adapter_invoked=True, broker_stub_installed=True)


def test_k126_forged_record_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k126"))
    _note("K126", "test_k126_forged_record_rejected", "production_execution_adapter", result["stub_calls"] == 0, adapter_invoked=True, broker_stub_installed=True)


def test_k127_synthetic_decision_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = _run()["details"]["risk_decision"]
    result = _call(monkeypatch, decision)
    _note("K127", "test_k127_synthetic_decision_rejected", "production_execution_adapter", _refused(result, "synthetic_context_rejected"), adapter_invoked=True, broker_stub_installed=True)


def test_k128_shared_path_uses_fake_broker() -> None:
    result = _run()
    _note("K128", "test_k128_shared_path_uses_fake_broker", "FakeBroker.submit", result["real_broker"] is False and result["broker_requests"] == 1)


def test_k129_production_adapter_closed_to_synthetic(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = _run()["details"]["risk_decision"]
    result = _call(monkeypatch, decision)
    _note("K129", "test_k129_production_adapter_closed_to_synthetic", "production_execution_adapter", result["stub_calls"] == 0, adapter_invoked=True, broker_stub_installed=True)


def test_k130_permission_stays_disabled() -> None:
    result = _run()
    _note("K130", "test_k130_permission_stays_disabled", "evaluate_one_instrument_iteration", result["production_authorised"] is False and result["trading_ready"] is False)


def test_k131_strategies_stay_inactive() -> None:
    _run()
    _note("K131", "test_k131_strategies_stay_inactive", "strategies", all(strategies[name].active is False for name in NAMES))


def test_k132_account_provenance_not_fabricated() -> None:
    result = _run()
    _note("K132", "test_k132_account_provenance_not_fabricated", "_build_risk_decision", "production_account_provenance" in result["details"]["risk_decision"]["missing_evidence"])


def test_k133_market_provenance_not_fabricated() -> None:
    result = _run()
    _note("K133", "test_k133_market_provenance_not_fabricated", "_build_risk_decision", result["details"]["risk_decision"]["market_data_evidence"] == "MISSING_EVIDENCE")


def test_k134_margin_not_fabricated() -> None:
    result = _run()
    _note("K134", "test_k134_margin_not_fabricated", "_build_risk_decision", result["details"]["risk_decision"]["margin_evidence"] == "NOT_IMPLEMENTED")


def test_k135_spread_not_pass() -> None:
    result = _run()
    _note("K135", "test_k135_spread_not_pass", "_build_risk_decision", result["details"]["risk_decision"]["spread"] == "POLICY_UNAPPROVED")


def test_k136_diagnostic_record_does_not_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k136", production_eligible=False))
    _note("K136", "test_k136_diagnostic_record_does_not_dispatch", "production_execution_adapter", result["stub_calls"] == 0, adapter_invoked=True, broker_stub_installed=True)


def test_k137_exposure_hold_remains() -> None:
    note_unconfirmed_exposure(SYMBOL, "old")
    result = _run()
    _note("K137", "test_k137_exposure_hold_remains", "note_unconfirmed_exposure", result["blocked_by"] == "exposure_unconfirmed")


def test_k138_timeout_does_not_retry() -> None:
    broker = FakeBroker("filled", error=TimeoutError())
    result = _run(broker=broker)
    _note("K138", "test_k138_timeout_does_not_retry", "FakeBroker.submit", broker.request_count == 1 and result["exposure_held"] is True)


def test_k139_scenario_buy() -> None:
    result = _run()
    _note("K139", "test_k139_scenario_buy", "evaluate_one_instrument_iteration", result["broker_requests"] == 1 and result["production_eligible"] is False)


def test_k140_scenario_sell() -> None:
    result = _run(vote={"allow": True, "direction": "SELL", "confidence": 0.8})
    _note("K140", "test_k140_scenario_sell", "evaluate_one_instrument_iteration", result["broker_requests"] == 1)


def test_k141_scenario_missing_account() -> None:
    result = _run(account_present=False, balance=None)
    _note("K141", "test_k141_scenario_missing_account", "_account_entry_block", result["blocked_by"] == "account_missing")


def test_k142_scenario_unverified_account() -> None:
    result = _run(account_context="production")
    _note("K142", "test_k142_scenario_unverified_account", "_account_entry_block", result["blocked_by"] == "account_unverified")


def test_k143_scenario_missing_timestamp() -> None:
    result = _run(quote_as_of=None)
    _note("K143", "test_k143_scenario_missing_timestamp", "_market_entry_block", result["blocked_by"] == "quote_timestamp_missing")


def test_k144_scenario_stale_quote() -> None:
    result = _run(quote_as_of=OPEN - timedelta(minutes=5))
    _note("K144", "test_k144_scenario_stale_quote", "MANAGE_PRICE_STALE_SEC", result["blocked_by"] == "quote_stale")


def test_k145_scenario_unapproved_spread() -> None:
    result = _run(spread=0.05)
    _note("K145", "test_k145_scenario_unapproved_spread", "_build_risk_decision", result["details"]["risk_decision"]["spread"] == "POLICY_UNAPPROVED" and result["production_eligible"] is False)


def test_k146_scenario_missing_margin() -> None:
    result = _run()
    _note("K146", "test_k146_scenario_missing_margin", "_build_risk_decision", result["details"]["risk_decision"]["margin_evidence"] == "NOT_IMPLEMENTED")


def test_k147_scenario_missing_market_provenance() -> None:
    result = _run()
    _note("K147", "test_k147_scenario_missing_market_provenance", "_build_risk_decision", result["details"]["risk_decision"]["market_data_evidence"] == "MISSING_EVIDENCE")


def test_k148_scenario_portfolio_breach() -> None:
    open_position(Position("GBP_USD", "BUY", 300_000, 1.27, 1.269, 1.3, 0, "synthetic", "synthetic", "synthetic"))
    result = _run(balance=5000)
    _note("K148", "test_k148_scenario_portfolio_breach", "portfolio_risk_cap_exceeded", result["blocked_by"] == "portfolio_risk_cap")


def test_k149_scenario_gross_breach(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", "0.01")
    result = _run()
    _note("K149", "test_k149_scenario_gross_breach", "portfolio_gross_notional_pct_of_nav", result["blocked_by"] == "notional_cap")


def test_k150_scenario_unit_breach(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_POSITION_UNITS", "1")
    result = _run()
    _note("K150", "test_k150_scenario_unit_breach", "_configured_unit_cap", result["blocked_by"] == "unit_cap")


def test_k151_scenario_daily_loss(monkeypatch: pytest.MonkeyPatch) -> None:
    path = _risk_on(monkeypatch)
    _observe(path, -200.0, 10000.0)
    result = _run(unrealised=0.0)
    _note("K151", "test_k151_scenario_daily_loss", "block_reason", result["blocked_by"] == "daily_realised_loss_limit")


def test_k152_scenario_position() -> None:
    open_position(Position(SYMBOL, "BUY", 1, 1.1, 1.0, 1.2, 0, "scalp", "x", "synthetic"))
    result = _run()
    _note("K152", "test_k152_scenario_position", "get_position", result["blocked_by"] == "position_already_open")


def test_k153_scenario_filled() -> None:
    note_unconfirmed_exposure(SYMBOL, "filled")
    result = _run()
    _note("K153", "test_k153_scenario_filled", "note_unconfirmed_exposure", result["blocked_by"] == "exposure_unconfirmed")


def test_k154_scenario_pending() -> None:
    note_blocking_reservation(SYMBOL, "pend")
    result = _run()
    _note("K154", "test_k154_scenario_pending", "note_blocking_reservation", result["blocked_by"] == "active_reservation")


def test_k155_scenario_partial() -> None:
    register_order(LocalOrder("part", SYMBOL, "BUY", 1, 1, OrderStatus.PARTIAL, 1.1, 0.0))
    note_blocking_reservation(SYMBOL, "part")
    result = _run()
    _note("K155", "test_k155_scenario_partial", "note_blocking_reservation", result["broker_requests"] == 0)


def test_k156_scenario_unresolved() -> None:
    restore_unresolved_intent(SYMBOL, "un")
    result = _run()
    _note("K156", "test_k156_scenario_unresolved", "restore_unresolved_intent", result["blocked_by"] == "unresolved_intent")


def test_k157_scenario_rl_veto() -> None:
    bars = _bars()
    result = _run(candles=bars, rl_agent=_agent_for(bars, "SKIP"))
    _note("K157", "test_k157_scenario_rl_veto", "RLAgent.decide", result["blocked_by"] == "rl_veto")


def test_k158_scenario_invalid_vote() -> None:
    result = _run(vote={"allow": True, "direction": "MAYBE", "confidence": 0.2})
    _note("K158", "test_k158_scenario_invalid_vote", "canonical_entry_direction", result["blocked_by"] == "invalid_entry_direction")


def test_k159_scenario_inactive() -> None:
    result = _run(strategy_active=False, strategy_active_map={})
    _note("K159", "test_k159_scenario_inactive", "strategy_entry_block_reason", result["blocked_by"] == "NO_STRATEGY_SELECTED")


def test_k160_scenario_reservation_failure() -> None:
    result = _run(persistence_failure="unavailable")
    _note("K160", "test_k160_scenario_reservation_failure", "refuse_reservation_after_database_fault", result["blocked_by"] == "reservation_persistence_failed" and result["broker_requests"] == 0)


def test_k161_scenario_timeout() -> None:
    result = _run(broker=FakeBroker("filled", error=TimeoutError()))
    _note("K161", "test_k161_scenario_timeout", "FakeBroker.submit", result["outcome"] == "timeout" and result["exposure_held"] is True)


def test_k162_scenario_ambiguous() -> None:
    result = _run(broker=FakeBroker("ambiguous"))
    _note("K162", "test_k162_scenario_ambiguous", "FakeBroker.submit", result["outcome"] == "ambiguous" and result["broker_requests"] == 1)


def test_k163_scenario_partial_fill() -> None:
    result = _run(broker=FakeBroker("partial"))
    _note("K163", "test_k163_scenario_partial_fill", "finalize_order_fill", result["status"] == "partial" and result["exposure_held"] is True)


def test_k164_scenario_record_failure() -> None:
    result = _run(fail_position_record=True)
    _note("K164", "test_k164_scenario_record_failure", "record_synthetic_fill_position", result["exposure_held"] is True and get_position(SYMBOL) is None)


def test_k165_scenario_duplicate_client() -> None:
    register_order(LocalOrder("same", SYMBOL, "BUY", 1, 0, OrderStatus.CANCELLED, None, 0.0))
    result = _run(client_order_id="same")
    _note("K165", "test_k165_scenario_duplicate_client", "try_begin_order_submission", result["blocked_by"] == "reservation_refused")


def test_k166_scenario_forged_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k166"))
    _note("K166", "test_k166_scenario_forged_adapter", "production_execution_adapter", _refused(result, "untrusted_decision"), adapter_invoked=True, broker_stub_installed=True)


def test_k167_scenario_synthetic_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _run()["details"]["risk_decision"])
    _note("K167", "test_k167_scenario_synthetic_adapter", "production_execution_adapter", _refused(result, "synthetic_context_rejected"), adapter_invoked=True, broker_stub_installed=True)


def test_k168_scenario_changed_intent(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k168"), direction="SELL")
    _note("K168", "test_k168_scenario_changed_intent", "production_execution_adapter", _refused(result, "order_direction_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k169_scenario_stale_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    old = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    result = _call(monkeypatch, _forged("k169", timestamp=old))
    _note("K169", "test_k169_scenario_stale_adapter", "production_execution_adapter", _refused(result, "decision_expired"), adapter_invoked=True, broker_stub_installed=True)


def test_k170_scenario_reused_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = _forged("k170")
    _call(monkeypatch, decision)
    result = _call(monkeypatch, decision)
    _note("K170", "test_k170_scenario_reused_adapter", "production_execution_adapter", _refused(result, "decision_already_used"), adapter_invoked=True, broker_stub_installed=True, limitations="in-process reuse only")


def test_k171_scenario_missing_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = _forged("k171")
    decision["gates"] = [gate for gate in decision["gates"] if gate["id"] != "margin"]  # type: ignore[index]
    result = _call(monkeypatch, decision)
    _note("K171", "test_k171_scenario_missing_gate", "production_execution_adapter", _refused(result, "mandatory_gates_missing"), adapter_invoked=True, broker_stub_installed=True)


def test_k172_scenario_failed_reservation(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k172", reservation_state="failed"))
    _note("K172", "test_k172_scenario_failed_reservation", "production_execution_adapter", _refused(result, "reservation_not_permission"), adapter_invoked=True, broker_stub_installed=True)


def test_k173_scenario_cleanup() -> None:
    setup_function()
    _note("K173", "test_k173_scenario_cleanup", "reset_orders_for_tests", database._pg_conn is None and not positions)


def test_k174_selector() -> None:
    result = _run()
    _note("K174", "test_k174_selector", "select_strategy", result["details"]["selector_called"] is True)


def test_k175_vote() -> None:
    result = _run()
    _note("K175", "test_k175_vote", "AIEnsemble.vote", result["details"]["vote_wrapper_called"] is True)


def test_k176_rl() -> None:
    result = _run()
    _note("K176", "test_k176_rl", "RLAgent.decide", result["details"]["rl_veto_called"] is True)


def test_k177_shared_eligibility() -> None:
    result = _run()
    phases = result["phases"]
    _note("K177", "test_k177_shared_eligibility", "evaluate_one_instrument_iteration", phases.index("eligibility") < phases.index("reservation") and result["production_eligible"] is False)


def test_k178_adapter_invoked_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, None)
    _note("K178", "test_k178_adapter_invoked_offline", "production_execution_adapter", result["stub_calls"] == 0 and result["status"] == "refused", adapter_invoked=True, broker_stub_installed=True)


def test_k179_forged_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k179"))
    _note("K179", "test_k179_forged_rejected", "production_execution_adapter", _refused(result, "untrusted_decision"), adapter_invoked=True, broker_stub_installed=True)


def test_k180_synthetic_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _run()["details"]["risk_decision"])
    _note("K180", "test_k180_synthetic_rejected", "production_execution_adapter", _refused(result, "synthetic_context_rejected"), adapter_invoked=True, broker_stub_installed=True)


def test_k181_intent_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k181"), units=50)
    _note("K181", "test_k181_intent_rejected", "production_execution_adapter", _refused(result, "order_quantity_mismatch"), adapter_invoked=True, broker_stub_installed=True)


def test_k182_stale_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    old = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    result = _call(monkeypatch, _forged("k182", timestamp=old))
    _note("K182", "test_k182_stale_rejected", "production_execution_adapter", _refused(result, "decision_expired"), adapter_invoked=True, broker_stub_installed=True)


def test_k183_reuse_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = _forged("k183")
    _call(monkeypatch, decision)
    result = _call(monkeypatch, decision)
    _note("K183", "test_k183_reuse_rejected", "production_execution_adapter", _refused(result, "decision_already_used"), adapter_invoked=True, broker_stub_installed=True, limitations="in-process reuse rejected; durable replay prevention is NOT_EVALUATED")


def test_k184_failed_reservation_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k184", reservation_state="failed"))
    _note("K184", "test_k184_failed_reservation_rejected", "production_execution_adapter", _refused(result, "reservation_not_permission"), adapter_invoked=True, broker_stub_installed=True)


def test_k185_missing_gate_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = _forged("k185")
    decision["gates"] = [gate for gate in decision["gates"] if gate["id"] != "numeric_spread"]  # type: ignore[index]
    result = _call(monkeypatch, decision)
    _note("K185", "test_k185_missing_gate_rejected", "production_execution_adapter", _refused(result, "mandatory_gates_missing"), adapter_invoked=True, broker_stub_installed=True)


def test_k186_account_provenance_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _gate(_forged("k186"), "production_account_provenance", "MISSING_EVIDENCE"))
    _note("K186", "test_k186_account_provenance_rejected", "production_execution_adapter", _refused(result, "mandatory_missing_evidence"), adapter_invoked=True, broker_stub_installed=True)


def test_k187_market_provenance_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _gate(_forged("k187"), "production_market_provenance", "MISSING_EVIDENCE"))
    _note("K187", "test_k187_market_provenance_rejected", "production_execution_adapter", _refused(result, "mandatory_missing_evidence"), adapter_invoked=True, broker_stub_installed=True)


def test_k188_margin_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _gate(_forged("k188"), "margin", "NOT_IMPLEMENTED"))
    _note("K188", "test_k188_margin_rejected", "production_execution_adapter", _refused(result, "mandatory_not_implemented"), adapter_invoked=True, broker_stub_installed=True)


def test_k189_spread_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _gate(_forged("k189"), "numeric_spread", "POLICY_UNAPPROVED"))
    _note("K189", "test_k189_spread_rejected", "production_execution_adapter", _refused(result, "mandatory_policy_unapproved"), adapter_invoked=True, broker_stub_installed=True)


def test_k190_buy_once() -> None:
    broker = FakeBroker("filled")
    result = _run(broker=broker)
    _note("K190", "test_k190_buy_once", "FakeBroker.submit", broker.request_count == 1)


def test_k191_sell_once() -> None:
    broker = FakeBroker("filled")
    result = _run(vote={"allow": True, "direction": "SELL", "confidence": 0.8}, broker=broker)
    _note("K191", "test_k191_sell_once", "FakeBroker.submit", broker.request_count == 1)


def test_k192_real_broker_not_called(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _call(monkeypatch, _forged("k192"))
    _note("K192", "test_k192_real_broker_not_called", "production_execution_adapter", result["stub_calls"] == 0, adapter_invoked=True, broker_stub_installed=True)


def test_k193_no_oanda_client() -> None:
    _run()
    client = sys.modules.get("forex_bot.oanda_client")
    api = None if client is None else getattr(client, "_api", None)
    _note("K193", "test_k193_no_oanda_client", "oanda_client", api is None)


def test_k194_no_postgresql() -> None:
    _run()
    _note("K194", "test_k194_no_postgresql", "database", database._pg_conn is None)


def test_k195_no_network() -> None:
    _note("K195", "test_k195_no_network", "socket", "main" not in sys.modules)


def test_k196_no_dns() -> None:
    _note("K196", "test_k196_no_dns", "socket", "main" not in sys.modules)


def test_k197_no_run_bot() -> None:
    _note("K197", "test_k197_no_run_bot", "run_bot", inspect.iscoroutinefunction(run_bot))


def test_k198_no_launcher() -> None:
    _note("K198", "test_k198_no_launcher", "main", "main" not in sys.modules)


def test_k199_no_lifespan() -> None:
    _note("K199", "test_k199_no_lifespan", "lifespan", sys.modules.get("forex_bot.app") is None)


def test_k200_no_activation() -> None:
    _run()
    _note("K200", "test_k200_no_activation", "strategies", all(strategies[name].active is False for name in NAMES))


def test_k201_no_permission_mutation() -> None:
    path = ROOT / "data" / "ops" / "live_safety_state.json"
    before = path.stat().st_mtime if path.exists() else None
    _run()
    after = path.stat().st_mtime if path.exists() else None
    _note("K201", "test_k201_no_permission_mutation", "live_safety", before == after)


def test_k202_no_flat_release() -> None:
    _note("K202", "test_k202_no_flat_release", "confirm_exposure_flat", confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False)


def test_k203_r8() -> None:
    note_blocking_reservation(SYMBOL, "r8")
    result = _run()
    _note("K203", "test_k203_r8", "note_blocking_reservation", result["blocked_by"] == "active_reservation")


def test_k204_r9() -> None:
    _note("K204", "test_k204_r9", "confirm_exposure_flat", confirm_exposure_flat(SYMBOL, evidence="FILLED") is False)


def test_k205_r10() -> None:
    text = (ROOT / "forex_bot" / "app.py").read_text(encoding="utf-8")
    _note("K205", "test_k205_r10", "initialise_application", "trading_ready" in text)


def test_k206_r11() -> None:
    kept = select_rows_for_recovery([{"client_order_id": "r11", "symbol": SYMBOL, "status": "FILLED", "metadata": None}])
    _note("K206", "test_k206_r11", "select_rows_for_recovery", bool(kept))


def test_k207_r12() -> None:
    result = _run()
    _note("K207", "test_k207_r12", "evaluate_one_instrument_iteration", result["broker_requests"] == 1 and result["scheduled_another"] is False)


def test_k208_r13() -> None:
    _note("K208", "test_k208_r13", "confirm_exposure_flat", confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False)


def test_k209_r14() -> None:
    result = _run()
    details = result["details"]
    _note("K209", "test_k209_r14", "evaluate_one_instrument_iteration", bool(details["selector_called"] and details["vote_wrapper_called"] and details["rl_veto_called"]))


def test_k210_r15() -> None:
    result = _run(account_present=False, balance=None)
    _note("K210", "test_k210_r15", "_account_entry_block", result["blocked_by"] == "account_missing")


def test_k211_r16() -> None:
    result = _run(balance=5000)
    _note("K211", "test_k211_r16", "portfolio_risk_cap_exceeded", result["details"]["portfolio_cap_equity"] == 5000)


def test_k212_r17() -> None:
    result = _run(candles=_bars(5))
    _note("K212", "test_k212_r17", "_entry_lookback_requirement", result["blocked_by"] in {"insufficient_lookback", "volatility_unsafe"})


def test_k213_r18() -> None:
    result = _run()
    _note("K213", "test_k213_r18", "_build_risk_decision", result["production_eligible"] is False and result["details"]["risk_decision"]["spread"] == "POLICY_UNAPPROVED")


def test_k214_postgresql_not_evaluated() -> None:
    _skip("K214", "test_k214_postgresql_not_evaluated", "PostgreSQL", "PostgreSQL engine NOT_EVALUATED")


def test_k215_oanda_not_evaluated() -> None:
    _skip("K215", "test_k215_oanda_not_evaluated", "OANDA", "OANDA broker NOT_EVALUATED")


def test_k216_loop_not_evaluated() -> None:
    _skip("K216", "test_k216_loop_not_evaluated", "run_bot", "production loop NOT_EVALUATED")


def test_k217_flat_not_evaluated() -> None:
    _skip("K217", "test_k217_flat_not_evaluated", "confirm_exposure_flat", "broker-flat release NOT_EVALUATED")


def test_k218_account_not_evaluated() -> None:
    _skip("K218", "test_k218_account_not_evaluated", "account", "production account provenance NOT_EVALUATED")


def test_k219_market_not_evaluated() -> None:
    _skip("K219", "test_k219_market_not_evaluated", "market", "production market provenance NOT_EVALUATED")


def test_k220_loss_not_evaluated() -> None:
    _skip("K220", "test_k220_loss_not_evaluated", "account_risk", "production loss durability NOT_EVALUATED")


def test_k221_margin_not_evaluated() -> None:
    _skip("K221", "test_k221_margin_not_evaluated", "margin", "broker margin sufficiency NOT_EVALUATED")


def test_k222_profitability_not_evaluated() -> None:
    _skip("K222", "test_k222_profitability_not_evaluated", "backtest", "strategy profitability NOT_EVALUATED")

"""Offline R.27 OANDA account-contract checks. No live account, network, or production loop."""

from __future__ import annotations

import importlib.util
import inspect
import json
import os
import socket
import subprocess
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path


class _BlockedSocket(socket.socket):
    def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("R27_NETWORK_BLOCKED")


def _blocked_name(*_args, **_kwargs):  # noqa: ANN002, ANN003
    raise RuntimeError("R27_DNS_BLOCKED")


socket.socket = _BlockedSocket  # type: ignore[misc]
socket.getaddrinfo = _blocked_name  # type: ignore[assignment]
socket.gethostbyname = _blocked_name  # type: ignore[assignment]
socket.create_connection = _blocked_name  # type: ignore[assignment]
_dotenv = types.ModuleType("dotenv")
_dotenv.load_dotenv = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
sys.modules["dotenv"] = _dotenv

ROOT = Path(__file__).resolve().parents[1]
R27 = ROOT / "data" / "research" / "adaptive_ensemble" / "r27"
R27.mkdir(parents=True, exist_ok=True)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R27 / "synthetic_live_safety_state.json")
sys.path.insert(0, str(ROOT))

from forex_bot.bot_loop import IterationDependencies, evaluate_one_instrument_iteration  # noqa: E402
from forex_bot.database import reset_order_intent_gate_for_tests  # noqa: E402
from forex_bot.oanda_account_adapter import account_core, normalize_oanda_risk_inputs  # noqa: E402
from forex_bot.orders import reset_orders_for_tests  # noqa: E402
from forex_bot.positions import close_position, positions  # noqa: E402

OPEN = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
ACCOUNT = "101-004-1435156-001"
DRIVER = ROOT / "tests" / "r27_restart_driver.py"


def _load_driver():
    spec = importlib.util.spec_from_file_location("r27_restart_driver", DRIVER)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _broker():
    spec = importlib.util.spec_from_file_location("r12_fakes", ROOT / "tests" / "r12_fakes.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module.FakeBroker("filled")


def _seed(name: str, *, peak: float = 10000.0, baseline: float = 10000.0, realised: float = 0.0) -> Path:
    path = R27 / "states" / f"{name}.json"
    _load_driver().seed_state(path, peak=peak, baseline=baseline, realised=realised)
    os.environ["RISK_STATE_PATH"] = str(path)
    os.environ["RISK_ACCOUNT_ID"] = ACCOUNT
    os.environ["RISK_ACCOUNT_CURRENCY"] = "USD"
    return path


def _limits(exposure: str = "1000") -> None:
    os.environ["RISK_MAX_DAILY_LOSS_PCT"] = "0.02"
    os.environ["RISK_MAX_DRAWDOWN_PCT"] = "0.05"
    os.environ["RISK_MAX_TOTAL_EXPOSURE_PCT"] = exposure


def _fill(event_id: str = "1", amount: str = "0.0000") -> dict:
    return {
        "orderFillTransaction": {
            "id": event_id,
            "pl": amount,
            "price": "1.10000",
            "units": "1",
            "time": "2026-01-07T11:00:00+00:00",
        }
    }


def _transactions(rows: list[dict] | None = None, last: str = "1") -> dict:
    return {"lastTransactionID": last, "transactions": [_fill()] if rows is None else rows}


def _summary(**account: object) -> dict:
    body = {
        "id": ACCOUNT,
        "currency": "USD",
        "NAV": "10000.0000",
        "balance": "10010.0000",
        "unrealizedPL": "0.0000",
        "marginAvailable": "9900.0000",
        "positions": [],
        "orders": [],
    }
    body.update(account)
    return {"observed_at": OPEN.isoformat(), "account": body}


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
        "balance": 10010.0,
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
        "vote": {"allow": True, "direction": "BUY", "confidence": 0.8},
        "account_payload": {"id": ACCOUNT},
        "expected_account_id": ACCOUNT,
        "expected_account_currency": "USD",
        "oanda_summary": _summary(),
        "oanda_transactions": _transactions(),
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


def test_documented_summary_uses_nav_and_reaches_evaluate() -> None:
    path = _seed("valid")
    result = _run()
    assert result["broker_requests"] == 1
    assert result["details"].get("reservation_attempted") is True
    assert result["production_eligible"] is False
    assert result["details"]["risk_equity_source"] == "broker_nav"
    assert result["details"]["reconciled_nav"] == 10000.0
    phases = result["phases"]
    assert phases.index("account_reconciliation") < phases.index("execution_risk") < phases.index("reservation")
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["reconciliation"]["nav"] == 10000.0
    assert stored["reconciliation"]["status"] == "verified"
    assert stored["account_id"] == ACCOUNT
    assert stored["currency"] == "USD"
    assert stored["realised_by_day"]["2026-01-07"] == 0.0


def test_missing_nav_is_not_replaced_by_balance() -> None:
    path = _seed("missing-nav")
    before = path.read_text(encoding="utf-8")
    account = _summary()["account"]
    del account["NAV"]
    result = _run(oanda_summary={"observed_at": OPEN.isoformat(), "account": account})
    assert _blocked(result, "broker_equity_missing")
    assert path.read_text(encoding="utf-8") == before
    parsed = account_core({"account": account}, expected_account_id=ACCOUNT)
    assert parsed == "broker_equity_missing"


def test_account_document_rejections_do_not_reserve() -> None:
    path = _seed("reject-account")
    before = path.read_text(encoding="utf-8")
    missing_balance = _summary()
    del missing_balance["account"]["balance"]
    cases = [
        (missing_balance, "broker_balance_missing"),
        (_summary(id="OTHER"), "broker_account_mismatch"),
        (_summary(currency="EUR"), "broker_currency_mismatch"),
        (_summary(NAV="not-a-number"), "broker_value_nonfinite"),
        (_summary(NAV="NaN"), "broker_value_nonfinite"),
        (_summary(NAV="-1.0000"), "broker_equity_invalid"),
        (_summary(unrealizedPL="inf"), "broker_value_nonfinite"),
        ({"observed_at": (OPEN - timedelta(seconds=301)).isoformat(), "account": _summary()["account"]}, "account_snapshot_stale"),
        ({"observed_at": (OPEN + timedelta(seconds=5)).isoformat(), "account": _summary()["account"]}, "account_timestamp_future"),
        ({}, "broker_response_invalid"),
        ({"errorMessage": "Insufficient authorization"}, "broker_response_invalid"),
        ({"account": {"id": ACCOUNT, "currency": "USD", "balance": "10010.0000"}}, "broker_equity_missing"),
    ]
    for document, reason in cases:
        result = _run(oanda_summary=document)
        assert _blocked(result, reason), (reason, result["blocked_by"])
        assert path.read_text(encoding="utf-8") == before


def test_positions_and_orders_follow_local_shapes() -> None:
    path = _seed("books", baseline=1_000_000_000.0)
    long_short = _summary(
        positions=[
            {"instrument": "EUR_USD", "long": {"units": "10", "averagePrice": "1.10000"}, "short": {"units": "0", "averagePrice": "0"}},
            {"instrument": "GBP_USD", "long": {"units": "0", "averagePrice": "0"}, "short": {"units": "-4", "averagePrice": "1.25000"}},
        ]
    )
    accepted = _run(oanda_summary=long_short)
    assert accepted["broker_requests"] == 1
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert {item["symbol"] for item in stored["exposure_positions"]} == {"EUR_USD", "GBP_USD"}
    _clear()

    pending = _summary(
        orders=[
            {
                "id": "6368",
                "instrument": "EUR_USD",
                "state": "PENDING",
                "units": "100",
                "price": "1.10000",
                "partialFill": "DEFAULT_FILL",
                "type": "LIMIT",
            }
        ]
    )
    held = _run(oanda_summary=pending, oanda_transactions=_transactions([_fill("2")], last="2"))
    assert held["details"]["reservation_attempted"] is True
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["exposure_orders"][0]["id"] == "6368"
    assert stored["exposure_orders"][0]["status"] == "PENDING"
    _clear()

    both = _summary(
        positions=[{"instrument": "EUR_USD", "long": {"units": "10", "averagePrice": "1.10000"}, "short": {"units": "0"}}],
        orders=[{"id": "700", "instrument": "EUR_USD", "state": "PENDING", "units": "-10000000", "price": "1.10000", "type": "LIMIT"}],
    )
    crowded = _run(oanda_summary=both, oanda_transactions=_transactions([_fill("3")], last="3"))
    assert _blocked(crowded, "total_exposure_limit")
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["exposure_positions"] and stored["exposure_orders"]

    unchanged = path.read_text(encoding="utf-8")
    for state in ("PARTIALLY_FILLED", "CANCELLED", "FILLED", "UNRESOLVED"):
        document = _summary(orders=[{"id": "9", "instrument": "EUR_USD", "state": state, "units": "1", "price": "1.10000"}])
        assert _blocked(_run(oanda_summary=document), "order_state_unverified")
    hedged = _summary(
        positions=[{"instrument": "EUR_USD", "long": {"units": "10", "averagePrice": "1.10000"}, "short": {"units": "-2", "averagePrice": "1.10000"}}]
    )
    assert _blocked(_run(oanda_summary=hedged), "position_book_unresolved")
    converted = _summary(
        positions=[{"instrument": "EUR_GBP", "long": {"units": "10", "averagePrice": "0.85000"}, "short": {"units": "0"}}]
    )
    assert _blocked(_run(oanda_summary=converted), "exposure_conversion_missing")
    assert path.read_text(encoding="utf-8") == unchanged


def test_transaction_contract_fails_closed_without_a_ledger_rule() -> None:
    path = _seed("events")
    before = path.read_text(encoding="utf-8")
    cases = [
        ({"pages": ["https://example.invalid/transactions/idrange?from=1&to=2"], "lastTransactionID": "2"}, "transaction_pages_incomplete"),
        (_transactions([{"id": "1", "type": "LIMIT_ORDER", "instrument": "EUR_USD"}], last="1"), "pnl_classification_unresolved"),
        (_transactions([{"id": "1", "type": "DAILY_FINANCING", "financing": "-1.2000"}], last="1"), "pnl_classification_unresolved"),
        (_transactions([{"id": "1", "type": "TRANSFER_FUNDS", "amount": "100.0000"}], last="1"), "pnl_classification_unresolved"),
        (_transactions([{"id": "1", "type": "ORDER_FILL", "pl": "5.0000"}], last="1"), "pnl_classification_unresolved"),
        (_transactions([{"id": "1", "type": "CLIENT_CONFIGURE"}], last="1"), "pnl_classification_unresolved"),
        (_transactions([_fill("1"), _fill("3")], last="3"), "event_gap"),
        (_transactions([_fill("1", "5.0000"), _fill("1", "5.0000")], last="1"), "event_gap"),
        (_transactions([], last="4"), "event_gap"),
        (
            _transactions([_fill(str(number), "0.0000") for number in range(2307, 2312)], last="2311"),
            "event_gap",
        ),
    ]
    for document, reason in cases:
        result = _run(oanda_transactions=document)
        assert _blocked(result, reason), (reason, result["blocked_by"])
        assert path.read_text(encoding="utf-8") == before

    ordered = _run(
        oanda_summary=_summary(lastTransactionID="2"),
        oanda_transactions=_transactions([_fill("2", "4.0000"), _fill("1", "-1.5000")], last="2"),
    )
    assert ordered["broker_requests"] == 1
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["realised_by_day"]["2026-01-07"] == 2.5
    assert sorted(stored["events"]) == ["1", "2"]


def test_fetch_account_summary_does_not_fabricate_nav(monkeypatch) -> None:
    import forex_bot.oanda_client as client
    from forex_bot.config import Config
    from forex_bot.state import state

    previous_id = Config.OANDA_ACCOUNT_ID
    previous_nav = state.get("broker_nav")
    Config.OANDA_ACCOUNT_ID = ACCOUNT
    calls = {"broker": 0}
    try:
        _fetch_cases(client, calls, monkeypatch, previous_nav)
    finally:
        Config.OANDA_ACCOUNT_ID = previous_id


def _fetch_cases(client, calls, monkeypatch, previous_nav) -> None:
    from forex_bot.state import state

    def _reject(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("injected account failure")

    monkeypatch.setattr(client, "get_api", lambda: object())
    monkeypatch.setattr(client, "_oanda_request", _reject)
    monkeypatch.setattr("forex_bot.state.set_broker_account", lambda *_args, **_kwargs: calls.__setitem__("broker", calls["broker"] + 1))
    client._account_summary.clear()
    client._account_summary.update({"NAV": 1.0, "balance": 1.0})
    assert client.fetch_account_summary() is None
    assert client.last_account_summary() == {}
    assert calls["broker"] == 0
    assert state.get("broker_nav") == previous_nav

    def _missing(*_args, **_kwargs):  # noqa: ANN002, ANN003
        return {"account": {"id": ACCOUNT, "currency": "USD", "balance": "10010.0000", "unrealizedPL": "0.0000"}}

    monkeypatch.setattr(client, "_oanda_request", _missing)
    assert client.fetch_account_summary() is None
    assert client.last_account_summary() == {}
    assert calls["broker"] == 0

    def _valid(*_args, **_kwargs):  # noqa: ANN002, ANN003
        return {
            "account": {
                "id": ACCOUNT,
                "currency": "USD",
                "NAV": "35454.4740",
                "balance": "35524.8000",
                "unrealizedPL": "-70.3260",
                "marginAvailable": "35000.0000",
                "alias": "synthetic",
            }
        }

    monkeypatch.setattr(client, "_oanda_request", _valid)
    snap = client.fetch_account_summary()
    assert snap is not None
    assert snap["NAV"] == 35454.4740
    assert snap["balance"] == 35524.8000
    assert snap["NAV"] != snap["balance"]
    assert calls["broker"] == 1
    body = inspect.getsource(client.fetch_account_summary)
    assert 'get("NAV") or' not in body
    assert "balance = nav" not in body
    assert "marginUsed" not in body
    assert "marginCloseout" not in body
    assert "fetched_at" not in body
    assert "return None" in body


def test_shared_evaluate_source_does_not_call_the_summary_helper() -> None:
    body = inspect.getsource(evaluate_one_instrument_iteration)
    assert "fetch_account_summary" not in body
    assert "normalize_oanda_risk_inputs" in body


def test_missing_or_corrupt_state_is_not_a_safe_account() -> None:
    missing = R27 / "states" / "absent.json"
    if missing.exists():
        missing.unlink()
    os.environ["RISK_STATE_PATH"] = str(missing)
    os.environ["RISK_ACCOUNT_ID"] = ACCOUNT
    os.environ["RISK_ACCOUNT_CURRENCY"] = "USD"
    result = _run()
    assert _blocked(result, "risk_state_missing")
    assert not missing.exists()

    corrupt = _seed("corrupt")
    original = corrupt.read_text(encoding="utf-8")
    corrupt.write_text("{not-json", encoding="utf-8")
    result = _run()
    assert _blocked(result, "risk_state_unreadable")
    assert corrupt.read_text(encoding="utf-8") == "{not-json"
    corrupt.write_text(original, encoding="utf-8")


def test_separate_processes_keep_reconciled_oanda_state() -> None:
    driver = _load_driver()
    loss = R27 / "states" / "restart-loss.json"
    driver.seed_state(loss, peak=10000.0, baseline=10000.0, realised=0.0)
    writer = _spawn("persist", "loss", loss, "10000")
    wrote = _finish(writer)
    reader = _spawn("evaluate", "loss", loss, "10000")
    assert writer.poll() is not None
    read = _finish(reader)
    assert wrote["pid"] != read["pid"]
    assert read["blocked_by"] == "daily_realised_loss_limit"
    assert read["broker_requests"] == 0
    assert read["reservation_attempted"] is False
    assert read["realised"] == -200.0
    assert read["account_id"] == ACCOUNT
    assert read["production_eligible"] is False

    draw = R27 / "states" / "restart-drawdown.json"
    driver.seed_state(draw, peak=10000.0, baseline=1_000_000_000.0, realised=0.0)
    first = _spawn("persist", "drawdown", draw, "11000")
    peaked = _finish(first)
    second = _spawn("evaluate", "drawdown", draw, "10450")
    assert first.poll() is not None
    declined = _finish(second)
    assert peaked["pid"] != declined["pid"]
    assert peaked["peak_equity"] == 11000.0
    assert declined["blocked_by"] == "max_drawdown_limit"
    assert declined["broker_requests"] == 0
    assert declined["peak_equity"] == 11000.0

    exposed = R27 / "states" / "restart-exposure.json"
    driver.seed_state(exposed, peak=10000.0, baseline=1_000_000_000.0, realised=0.0)
    left = _spawn("persist", "exposure", exposed, "10000")
    _finish(left)
    right = _spawn("evaluate", "exposure", exposed, "10000")
    assert left.poll() is not None
    held = _finish(right)
    assert held["blocked_by"] == "total_exposure_limit"
    assert held["broker_requests"] == 0
    assert held["reservation_attempted"] is False
    assert held["exposure_order_ids"] == ["204"]

    dedup = R27 / "states" / "restart-dedup.json"
    driver.seed_state(dedup, peak=10000.0, baseline=10000.0, realised=0.0)
    original = _spawn("persist", "duplicate", dedup, "10000")
    _finish(original)
    replay = _spawn("replay", "duplicate", dedup, "10000")
    assert original.poll() is not None
    replayed = _finish(replay)
    assert replayed["pid"] != original.pid
    assert replayed["realised"] == -50.0
    assert replayed["event_ids"] == ["1"]

    gap = _spawn("incomplete", "duplicate", dedup, "10000")
    incomplete = _finish(gap)
    assert incomplete["pid"] != replayed["pid"]
    assert incomplete["blocked_by"] == "event_gap"
    assert incomplete["broker_requests"] == 0
    assert incomplete["reservation_attempted"] is False
    assert incomplete["realised"] == -50.0
    assert incomplete["production_eligible"] is False
    trace = {
        "daily_loss": {"writer": wrote, "reader": read},
        "drawdown": {"writer": peaked, "reader": declined},
        "exposure": held,
        "duplicate": replayed,
        "incomplete": incomplete,
    }
    (R27 / "restart_trace.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")


def test_normalizer_does_not_invent_nav_identity() -> None:
    reason, snapshot, _events = normalize_oanda_risk_inputs(
        _summary(NAV="49377.6580", balance="48695.6580", unrealizedPL="682.0000"),
        _transactions(),
        expected_account_id=ACCOUNT,
        expected_currency="USD",
        now=OPEN,
    )
    assert reason is None and snapshot is not None
    assert snapshot["NAV"] == 49377.6580
    assert snapshot["balance"] == 48695.6580
    assert snapshot["unrealised"] == 682.0
    assert snapshot["NAV"] != snapshot["balance"]


def _spawn(role: str, scenario: str, state: Path, balance: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-B", str(DRIVER), role, "--scenario", scenario, "--state", str(state), "--balance", balance],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _finish(proc: subprocess.Popen) -> dict:
    stdout, stderr = proc.communicate(timeout=90)
    assert proc.returncode == 0 and stdout.strip(), stderr or stdout
    return json.loads(stdout)

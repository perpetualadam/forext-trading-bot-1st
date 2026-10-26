"""Offline R.25 risk-limit checks. No broker, database service, or production loop."""

from __future__ import annotations

import importlib.util
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R25 = ROOT / "data" / "research" / "adaptive_ensemble" / "r25"
R25.mkdir(parents=True, exist_ok=True)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R25 / "synthetic_live_safety_state.json")
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from forex_bot.bot_loop import IterationDependencies, evaluate_one_instrument_iteration  # noqa: E402
from forex_bot.database import (  # noqa: E402
    note_blocking_reservation,
    note_unconfirmed_exposure,
    reset_order_intent_gate_for_tests,
)
from forex_bot.execution_risk import apply_realised_delta, load_offline_harness  # noqa: E402
from forex_bot.orders import LocalOrder, OrderStatus, register_order, reset_orders_for_tests  # noqa: E402
from forex_bot.positions import Position, close_position, open_position, positions  # noqa: E402

OPEN = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
DAY = "2026-01-07"
DRIVER = ROOT / "tests" / "r25_restart_driver.py"


def _broker():
    spec = importlib.util.spec_from_file_location("r12_fakes", ROOT / "tests" / "r12_fakes.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module.FakeBroker("filled")


def _bars() -> list[dict[str, float | str]]:
    return [
        {
            "open": 1.1,
            "high": 1.1002,
            "low": 1.0998,
            "close": 1.1,
            "time": "2026-01-07T11:58:00+00:00" if index == 49 else f"2026-01-07T10:{index % 60:02d}:00+00:00",
        }
        for index in range(50)
    ]


def _book(name: str, *, peak: float, baseline: float, realised: float) -> Path:
    path = R25 / "states" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "peak_equity": peak,
                "day_baselines": {DAY: baseline},
                "realised_by_day": {DAY: realised},
                "account_id": "synthetic-offline",
                "currency": "USD",
                "revision": 1,
                "events": {},
                "exposure_positions": [],
                "exposure_orders": [],
                "reconciliation": {
                    "status": "synthetic_offline",
                    "account_id": "synthetic-offline",
                    "currency": "USD",
                    "snapshot_id": "synthetic-seed",
                    "as_of": "2026-01-07T12:00:00+00:00",
                    "equity_source": "synthetic_seed",
                    "sequence_evidence": "absent",
                    "last_sequence": None,
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    os.environ["RISK_STATE_PATH"] = str(path)
    return path


def _limits(daily: str = "0.02", drawdown: str = "0.05", exposure: str = "1000") -> None:
    os.environ["RISK_MAX_DAILY_LOSS_PCT"] = daily
    os.environ["RISK_MAX_DRAWDOWN_PCT"] = drawdown
    os.environ["RISK_MAX_TOTAL_EXPOSURE_PCT"] = exposure


def _run(symbol: str = "EUR_USD", **overrides: object) -> dict:
    broker = overrides.pop("broker", None) or _broker()
    values: dict[str, object] = {
        "candles": _bars(),
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
        "vote": {"allow": True, "direction": "BUY", "confidence": 0.8},
    }
    values.update(overrides)
    result = evaluate_one_instrument_iteration(symbol, IterationDependencies(**values))  # type: ignore[arg-type]
    result["broker_requests"] = broker.request_count
    return result


def _clear() -> None:
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    for symbol in list(positions):
        close_position(symbol)


def setup_function() -> None:
    load_offline_harness(R25)
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    _clear()


def _blocked(result: dict, reason: str) -> bool:
    return (
        result["blocked_by"] == reason
        and result["broker_requests"] == 0
        and result["details"].get("reservation_attempted") is False
        and result["production_eligible"] is False
    )


def test_within_each_limit_can_reach_inert_dispatch() -> None:
    _limits()
    _book("within", peak=10000.0, baseline=10000.0, realised=0.0)
    result = _run(balance=9600.0, unrealised=-10.0)
    assert result["broker_requests"] == 1
    assert result["details"].get("reservation_attempted") is True
    assert result["blocked_by"] in ("", None)
    assert result["production_eligible"] is False


def test_daily_loss_boundary() -> None:
    _limits()
    _book("daily-at", peak=10000.0, baseline=10000.0, realised=-200.0)
    at_limit = _run()
    assert _blocked(at_limit, "daily_realised_loss_limit")
    _clear()
    _book("daily-inside", peak=10000.0, baseline=10000.0, realised=-199.0)
    inside = _run()
    assert inside["broker_requests"] == 1
    _clear()
    _book("daily-total", peak=10000.0, baseline=10000.0, realised=-100.0)
    total = _run(unrealised=-100.0)
    assert _blocked(total, "daily_total_loss_limit")


def test_drawdown_boundary() -> None:
    _limits()
    _book("dd-at", peak=10000.0, baseline=1_000_000_000.0, realised=0.0)
    at_limit = _run(balance=9500.0)
    assert _blocked(at_limit, "max_drawdown_limit")
    _clear()
    _book("dd-inside", peak=10000.0, baseline=1_000_000_000.0, realised=0.0)
    inside = _run(balance=9600.0)
    assert inside["broker_requests"] == 1


def test_exposure_boundary_and_outstanding_orders() -> None:
    _book("exposure", peak=10000.0, baseline=1_000_000_000.0, realised=0.0)
    _limits(exposure="1")
    measured = _run()
    assert measured["blocked_by"] == "total_exposure_limit"
    proposed = float(measured["details"]["proposed_exposure"])
    _clear()
    _book("exposure-at", peak=10000.0, baseline=1_000_000_000.0, realised=0.0)
    _limits(exposure=format(proposed / 10000.0, ".17g"))
    at_cap = _run()
    assert at_cap["broker_requests"] == 1
    assert abs(float(at_cap["details"]["proposed_exposure"]) - float(at_cap["details"]["exposure_cap"])) <= 1e-6
    _clear()
    _book("exposure-over", peak=10000.0, baseline=1_000_000_000.0, realised=0.0)
    _limits(exposure=format((proposed / 10000.0) * 0.5, ".17g"))
    beyond = _run()
    assert _blocked(beyond, "total_exposure_limit")
    _clear()
    _limits(exposure="20")
    register_order(LocalOrder("pend-gbp", "GBP_USD", "BUY", 1_000_000, 0, OrderStatus.PENDING, 1.27, 0.0))
    note_blocking_reservation("GBP_USD", "pend-gbp")
    pending = _run()
    assert _blocked(pending, "total_exposure_limit")
    _clear()
    register_order(LocalOrder("pend-gap", "GBP_USD", "BUY", 10, 0, OrderStatus.PENDING, None, 0.0))
    note_blocking_reservation("GBP_USD", "pend-gap")
    missing = _run()
    assert _blocked(missing, "exposure_unreadable")


def test_limit_configuration_failures_block() -> None:
    _book("config", peak=10000.0, baseline=10000.0, realised=0.0)
    cases = (
        ("RISK_MAX_DAILY_LOSS_PCT", "", "daily_loss_limit_unconfigured"),
        ("RISK_MAX_DAILY_LOSS_PCT", "off", "daily_loss_limit_disabled"),
        ("RISK_MAX_DAILY_LOSS_PCT", "abc", "daily_loss_limit_malformed"),
        ("RISK_MAX_DAILY_LOSS_PCT", "nan", "daily_loss_limit_nonfinite"),
        ("RISK_MAX_DRAWDOWN_PCT", "", "drawdown_limit_unconfigured"),
        ("RISK_MAX_TOTAL_EXPOSURE_PCT", "0", "exposure_limit_disabled"),
    )
    for name, value, reason in cases:
        _limits()
        if value == "":
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
        result = _run()
        assert _blocked(result, reason), result["blocked_by"]
        _clear()


def test_missing_stale_negative_and_unreadable_state_block() -> None:
    _limits()
    _book("account", peak=10000.0, baseline=10000.0, realised=0.0)
    missing_time = _run(account_as_of=None)
    assert _blocked(missing_time, "account_snapshot_timestamp_missing")
    stale = _run(account_as_of=OPEN - timedelta(seconds=301))
    assert stale["blocked_by"] == "account_snapshot_stale" and stale["broker_requests"] == 0
    negative = _run(balance=-5)
    assert negative["blocked_by"] == "account_equity_not_positive" and negative["broker_requests"] == 0
    missing_upl = _run(unrealised=None)
    assert _blocked(missing_upl, "account_unrealised_unavailable")
    os.environ["RISK_STATE_PATH"] = str(R25 / "states" / "absent.json")
    assert _blocked(_run(), "risk_state_missing")
    broken = R25 / "states" / "broken.json"
    broken.write_text("{", encoding="utf-8")
    os.environ["RISK_STATE_PATH"] = str(broken)
    assert _blocked(_run(), "risk_state_unreadable")
    inconsistent = _book("bad-peak", peak=10000.0, baseline=10000.0, realised=0.0)
    blob = json.loads(inconsistent.read_text(encoding="utf-8"))
    blob["peak_equity"] = "nope"
    inconsistent.write_text(json.dumps(blob), encoding="utf-8")
    assert _blocked(_run(), "risk_state_inconsistent")


def test_repeated_evaluation_stays_blocked() -> None:
    _limits()
    _book("repeat", peak=10000.0, baseline=10000.0, realised=-200.0)
    first = _run()
    second = _run()
    assert _blocked(first, "daily_realised_loss_limit")
    assert _blocked(second, "daily_realised_loss_limit")


def test_recovery_holds_still_precede_risk_dispatch() -> None:
    _limits()
    _book("holds", peak=10000.0, baseline=10000.0, realised=0.0)
    note_unconfirmed_exposure("EUR_USD", "cid-filled")
    filled = _run()
    assert filled["blocked_by"] == "exposure_unconfirmed" and filled["broker_requests"] == 0
    assert "execution_risk" not in filled["phases"]
    _clear()
    from forex_bot.database import restore_unresolved_intent

    restore_unresolved_intent("GBP_USD", "cid-unresolved")
    unresolved = _run("GBP_USD", price=1.27, bid=1.26995, ask=1.27005, stop_loss=1.269, take_profit=1.272)
    assert unresolved["blocked_by"] == "unresolved_intent" and unresolved["broker_requests"] == 0
    _clear()
    note_blocking_reservation("AUD_USD", "cid-pending")
    pending = _run("AUD_USD", price=0.65, bid=0.64995, ask=0.65005, stop_loss=0.649, take_profit=0.652)
    assert pending["blocked_by"] == "active_reservation" and pending["broker_requests"] == 0


def _spawn(role: str, state: Path, balance: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-B", str(DRIVER), role, "--state", str(state), "--balance", balance],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _finish(proc: subprocess.Popen) -> dict:
    stdout, stderr = proc.communicate(timeout=60)
    assert proc.returncode == 0, stderr
    return json.loads(stdout)


def test_restart_preserves_daily_loss_and_drawdown() -> None:
    _limits()
    loss_path = _book("restart-loss", peak=10000.0, baseline=10000.0, realised=0.0)
    writer = _spawn("record-loss", loss_path, "10000")
    loss_trace = _finish(writer)
    assert loss_trace["exit_pid"] == loss_trace["pid"]
    reader = _spawn("evaluate", loss_path, "10000")
    assert writer.poll() is not None
    loss_read = _finish(reader)
    assert loss_trace["pid"] != loss_read["pid"]
    assert loss_read["blocked_by"] == "daily_realised_loss_limit"
    assert loss_read["broker_requests"] == 0
    assert loss_read["reservation_attempted"] is False

    draw_path = _book("restart-drawdown", peak=10000.0, baseline=1_000_000_000.0, realised=0.0)
    first = _spawn("evaluate", draw_path, "10000")
    draw_write = _finish(first)
    assert draw_write["blocked_by"] in ("", None)
    assert draw_write["broker_requests"] == 1
    second = _spawn("evaluate", draw_path, "9400")
    assert first.poll() is not None
    draw_read = _finish(second)
    assert draw_write["pid"] != draw_read["pid"]
    assert draw_read["blocked_by"] == "max_drawdown_limit"
    assert draw_read["broker_requests"] == 0
    document = {
        "daily_loss": {"writer": loss_trace, "reader": loss_read},
        "drawdown": {"writer": draw_write, "reader": draw_read},
    }
    (R25 / "restart_trace.json").write_text(json.dumps(document, indent=2), encoding="utf-8")


def test_nonfinite_numbers_do_not_pass() -> None:
    _limits()
    _book("nonfinite", peak=10000.0, baseline=10000.0, realised=0.0)
    result = _run(unrealised=float("nan"))
    assert _blocked(result, "account_unrealised_unavailable")
    assert not math.isfinite(float("nan"))

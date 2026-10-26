"""Offline R.26 broker reconciliation. No live account, network, or production loop."""

from __future__ import annotations

import importlib.util
import json
import os
import socket
import stat
import subprocess
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path


class _BlockedSocket(socket.socket):
    def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("R26_NETWORK_BLOCKED")


def _blocked_name(*_args, **_kwargs):  # noqa: ANN002, ANN003
    raise RuntimeError("R26_DNS_BLOCKED")


socket.socket = _BlockedSocket  # type: ignore[misc]
socket.getaddrinfo = _blocked_name  # type: ignore[assignment]
socket.gethostbyname = _blocked_name  # type: ignore[assignment]
socket.create_connection = _blocked_name  # type: ignore[assignment]
_dotenv = types.ModuleType("dotenv")
_dotenv.load_dotenv = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
sys.modules["dotenv"] = _dotenv

ROOT = Path(__file__).resolve().parents[1]
R26 = ROOT / "data" / "research" / "adaptive_ensemble" / "r26"
R26.mkdir(parents=True, exist_ok=True)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R26 / "synthetic_live_safety_state.json")
sys.path.insert(0, str(ROOT))

from forex_bot.bot_loop import IterationDependencies, evaluate_one_instrument_iteration  # noqa: E402
from forex_bot.database import (  # noqa: E402
    note_blocking_reservation,
    note_unconfirmed_exposure,
    reset_order_intent_gate_for_tests,
)
from forex_bot.orders import reset_orders_for_tests  # noqa: E402
from forex_bot.positions import close_position, positions  # noqa: E402

OPEN = datetime(2026, 1, 7, 12, 0, tzinfo=timezone.utc)
ACCOUNT = "ACCT-R26"
DRIVER = ROOT / "tests" / "r26_restart_driver.py"


def _load_driver():
    spec = importlib.util.spec_from_file_location("r26_restart_driver", DRIVER)
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
    path = R26 / "states" / f"{name}.json"
    _load_driver().seed_state(path, peak=peak, baseline=baseline, realised=realised)
    os.environ["RISK_STATE_PATH"] = str(path)
    os.environ["RISK_ACCOUNT_ID"] = ACCOUNT
    os.environ["RISK_ACCOUNT_CURRENCY"] = "USD"
    return path


def _limits(exposure: str = "1000") -> None:
    os.environ["RISK_MAX_DAILY_LOSS_PCT"] = "0.02"
    os.environ["RISK_MAX_DRAWDOWN_PCT"] = "0.05"
    os.environ["RISK_MAX_TOTAL_EXPOSURE_PCT"] = exposure


def _snap(nav: float = 10000.0, **extra: object) -> dict:
    as_of = extra.pop("as_of", OPEN)
    body = {
        "provenance": extra.pop("provenance", "injected_synthetic"),
        "id": extra.pop("id", ACCOUNT),
        "currency": extra.pop("currency", "USD"),
        "snapshot_id": extra.pop("snapshot_id", "snap-1"),
        "as_of": as_of,
        "NAV": extra.pop("NAV", nav),
        "balance": extra.pop("balance", nav),
        "unrealised": extra.pop("unrealised", 0.0),
        "positions": extra.pop("positions", []),
        "orders": extra.pop("orders", []),
    }
    body.update(extra)
    return body


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
        "account_payload": {"id": ACCOUNT},
        "expected_account_id": ACCOUNT,
        "expected_account_currency": "USD",
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


def test_valid_snapshot_dispatches_on_broker_nav() -> None:
    path = _seed("valid")
    result = _run(balance=10000.0, broker_snapshot=_snap(9600.0, balance=10000.0, unrealised=-10.0))
    assert result["broker_requests"] == 1
    assert result["details"].get("reservation_attempted") is True
    assert result["production_eligible"] is False
    assert result["details"]["risk_equity_source"] == "broker_nav"
    assert result["details"]["reconciled_nav"] == 9600.0
    phases = result["phases"]
    assert phases.index("account_reconciliation") < phases.index("execution_risk") < phases.index("reservation")
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["reconciliation"]["equity_source"] == "broker_nav"
    assert stored["reconciliation"]["nav"] == 9600.0
    assert stored["peak_equity"] == 10000.0


def test_snapshot_rejections_do_not_reserve() -> None:
    path = _seed("reject")
    before = path.read_text(encoding="utf-8")
    cases = [
        (_snap(id="OTHER"), "broker_account_mismatch"),
        (_snap(currency="GBP"), "broker_currency_mismatch"),
        (_snap(provenance="live"), "broker_provenance_rejected"),
        (
            {
                "provenance": "injected_synthetic",
                "id": ACCOUNT,
                "currency": "USD",
                "snapshot_id": "missing-nav",
                "as_of": OPEN,
                "balance": 10000.0,
                "unrealised": 0.0,
            },
            "broker_equity_missing",
        ),
        (_snap(as_of=OPEN - timedelta(seconds=301)), "account_snapshot_stale"),
        (_snap(as_of=OPEN + timedelta(seconds=1)), "account_timestamp_future"),
        (_snap(NAV=float("nan")), "broker_value_nonfinite"),
        (_snap(NAV=-1), "broker_equity_invalid"),
        (_snap(equity=9000.0), "account_values_inconsistent"),
    ]
    for snapshot, reason in cases:
        result = _run(broker_snapshot=snapshot)
        assert _blocked(result, reason), result["blocked_by"]
        assert path.read_text(encoding="utf-8") == before
        _clear()


def test_duplicate_and_stale_order_snapshots_do_not_rewrite_the_peak() -> None:
    path = _seed("order", peak=10000.0)
    first = _run(broker_snapshot=_snap(12000.0, snapshot_id="snap-high", as_of=OPEN - timedelta(seconds=30)))
    assert first["broker_requests"] == 1
    _clear()
    raised = json.loads(path.read_text(encoding="utf-8"))
    assert raised["peak_equity"] == 12000.0
    revision = raised["revision"]
    older = _run(broker_snapshot=_snap(9000.0, snapshot_id="snap-old", as_of=OPEN - timedelta(seconds=60)))
    assert _blocked(older, "snapshot_out_of_order")
    conflict = _run(broker_snapshot=_snap(10000.0, snapshot_id="snap-high", as_of=OPEN - timedelta(seconds=30)))
    assert _blocked(conflict, "snapshot_conflict")
    repeat = _run(broker_snapshot=_snap(12000.0, snapshot_id="snap-high", as_of=OPEN - timedelta(seconds=30)))
    assert repeat["broker_requests"] == 1
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["peak_equity"] == 12000.0
    assert stored["revision"] == revision


def test_event_ledger_is_idempotent_and_fail_closed() -> None:
    path = _seed("events")
    trade = {"id": "e1", "kind": "trade_pl", "amount": -40.0, "time": "2026-01-07T11:00:00+00:00", "sequence": 2}
    earlier = {"id": "e0", "kind": "trade_pl", "amount": -10.0, "time": "2026-01-07T10:00:00+00:00", "sequence": 1}
    result = _run(broker_snapshot=_snap(), broker_events=[trade, earlier])
    assert result["broker_requests"] == 1
    assert json.loads(path.read_text(encoding="utf-8"))["realised_by_day"]["2026-01-07"] == -50.0
    _clear()
    again = _run(broker_snapshot=_snap(), broker_events=[earlier, trade])
    assert again["broker_requests"] == 1
    assert json.loads(path.read_text(encoding="utf-8"))["realised_by_day"]["2026-01-07"] == -50.0
    _clear()
    gap_path = _seed("gap")
    before = gap_path.read_text(encoding="utf-8")
    gap = _run(
        broker_snapshot=_snap(snapshot_id="gap", expected_sequence_end=3),
        broker_events=[
            {"id": "g1", "kind": "trade_pl", "amount": -5.0, "time": OPEN.isoformat(), "sequence": 1},
            {"id": "g3", "kind": "trade_pl", "amount": -5.0, "time": OPEN.isoformat(), "sequence": 3},
        ],
    )
    assert _blocked(gap, "event_gap")
    assert gap_path.read_text(encoding="utf-8") == before
    missing = _run(broker_snapshot=_snap(snapshot_id="noseq", expected_sequence_end=2))
    assert _blocked(missing, "event_gap")
    for kind, reason in (
        ("financing", "pnl_classification_unresolved"),
        ("fee", "pnl_classification_unresolved"),
        ("transfer", "pnl_classification_unresolved"),
        ("correction", "correction_target_missing"),
    ):
        _clear()
        case_path = _seed(kind)
        case_before = case_path.read_text(encoding="utf-8")
        blocked = _run(
            broker_snapshot=_snap(snapshot_id=kind),
            broker_events=[{"id": kind, "kind": kind, "amount": -5.0, "time": OPEN.isoformat()}],
        )
        assert _blocked(blocked, reason), blocked["blocked_by"]
        assert case_path.read_text(encoding="utf-8") == case_before
    _clear()
    reverse_path = _seed("reverse")
    _run(broker_snapshot=_snap(snapshot_id="base"), broker_events=[{"id": "e1", "kind": "trade_pl", "amount": -25.0, "time": OPEN.isoformat()}])
    _clear()
    _run(
        broker_snapshot=_snap(snapshot_id="base"),
        broker_events=[
            {"id": "e1", "kind": "trade_pl", "amount": -25.0, "time": OPEN.isoformat()},
            {"id": "rev", "kind": "reversal", "reverses": "e1", "amount": 25.0, "time": OPEN.isoformat()},
        ],
    )
    assert json.loads(reverse_path.read_text(encoding="utf-8"))["realised_by_day"]["2026-01-07"] == 0.0


def test_daily_loss_and_drawdown_use_reconciled_values() -> None:
    _seed("loss-at")
    at_limit = _run(
        broker_snapshot=_snap(),
        broker_events=[{"id": "loss", "kind": "trade_pl", "amount": -200.0, "time": OPEN.isoformat()}],
    )
    assert _blocked(at_limit, "daily_realised_loss_limit")
    _clear()
    _seed("loss-in")
    inside = _run(
        broker_snapshot=_snap(),
        broker_events=[{"id": "loss", "kind": "trade_pl", "amount": -199.0, "time": OPEN.isoformat()}],
    )
    assert inside["broker_requests"] == 1
    _clear()
    _seed("loss-over")
    beyond = _run(
        broker_snapshot=_snap(),
        broker_events=[{"id": "loss", "kind": "trade_pl", "amount": -201.0, "time": OPEN.isoformat()}],
    )
    assert _blocked(beyond, "daily_realised_loss_limit")
    _clear()
    _seed("loss-total")
    total = _run(
        balance=10000.0,
        unrealised=0.0,
        broker_snapshot=_snap(unrealised=-100.0),
        broker_events=[{"id": "loss", "kind": "trade_pl", "amount": -100.0, "time": OPEN.isoformat()}],
    )
    assert _blocked(total, "daily_total_loss_limit")
    _clear()
    peak_path = _seed("peak", peak=10000.0)
    raised = _run(broker_snapshot=_snap(11000.0, snapshot_id="peak", as_of=OPEN - timedelta(seconds=20)))
    assert raised["broker_requests"] == 1
    assert json.loads(peak_path.read_text(encoding="utf-8"))["peak_equity"] == 11000.0
    _clear()
    decline = _run(balance=10000.0, broker_snapshot=_snap(10450.0, snapshot_id="down", as_of=OPEN))
    assert _blocked(decline, "max_drawdown_limit")
    assert json.loads(peak_path.read_text(encoding="utf-8"))["peak_equity"] == 11000.0
    _clear()
    nav_path = _seed("nav-wins", peak=10000.0)
    nav_block = _run(balance=10000.0, broker_snapshot=_snap(9500.0, balance=10000.0))
    assert _blocked(nav_block, "max_drawdown_limit")
    assert nav_block["details"]["reconciled_nav"] == 9500.0
    assert json.loads(nav_path.read_text(encoding="utf-8"))["reconciliation"]["balance"] == 10000.0


def test_exposure_includes_reconciled_book_without_double_counting() -> None:
    _seed("measure")
    _limits(exposure="1")
    measured = _run(broker_snapshot=_snap())
    assert measured["blocked_by"] == "total_exposure_limit"
    proposed = float(measured["details"]["proposed_exposure"])
    _clear()
    _seed("at-cap")
    _limits(exposure=format((proposed / 10000.0), ".17g"))
    at_cap = _run(broker_snapshot=_snap(snapshot_id="at"))
    assert at_cap["broker_requests"] == 1
    _clear()
    _seed("over-cap")
    _limits(exposure=format((proposed / 10000.0) * 0.5, ".17g"))
    over = _run(broker_snapshot=_snap(snapshot_id="over"))
    assert _blocked(over, "total_exposure_limit")
    _clear()
    _seed("book")
    _limits(exposure="20")
    pending = _run(
        broker_snapshot=_snap(
            snapshot_id="pending",
            orders=[{"id": "pend", "symbol": "GBP_USD", "status": "PENDING", "units": 1_000_000, "price": 1.27}],
        )
    )
    assert _blocked(pending, "total_exposure_limit")
    _clear()
    filled_path = _seed("filled-book")
    _limits(exposure="1000")
    filled = _run(
        broker_snapshot=_snap(
            snapshot_id="filled",
            positions=[{"symbol": "GBP_USD", "units": 1000, "price": 1.27}],
            orders=[{"id": "done", "symbol": "GBP_USD", "status": "FILLED", "units": 1000, "price": 1.27}],
        )
    )
    assert filled["broker_requests"] == 1
    stored = json.loads(filled_path.read_text(encoding="utf-8"))
    assert stored["exposure_orders"] == []
    assert stored["exposure_positions"][0]["notional_account_ccy"] == 1270.0
    _clear()
    _seed("partial")
    _limits(exposure="12")
    partial = _run(
        broker_snapshot=_snap(
            snapshot_id="partial",
            orders=[
                {"id": "part", "symbol": "GBP_USD", "status": "PARTIAL", "units": 10000, "price": 1.27},
                {"id": "open", "symbol": "AUD_USD", "status": "UNRESOLVED", "units": 10000, "price": 0.65},
            ],
        )
    )
    assert _blocked(partial, "total_exposure_limit")
    assert partial["details"]["existing_exposure"] == 12700.0 + 6500.0
    _clear()
    _seed("convert")
    _limits(exposure="1000")
    missing_rate = _run(
        broker_snapshot=_snap(snapshot_id="jpy-missing", positions=[{"symbol": "USD_JPY", "units": 1000, "price": 150.0}])
    )
    assert _blocked(missing_rate, "exposure_conversion_missing")
    stale_rate = _run(
        broker_snapshot=_snap(
            snapshot_id="jpy-stale",
            positions=[
                {
                    "symbol": "USD_JPY",
                    "units": 1000,
                    "price": 150.0,
                    "conversion_price": 0.0067,
                    "conversion_as_of": (OPEN - timedelta(seconds=301)).isoformat(),
                }
            ],
        )
    )
    assert _blocked(stale_rate, "conversion_price_stale")
    converted = _run(
        broker_snapshot=_snap(
            snapshot_id="jpy",
            positions=[
                {
                    "symbol": "USD_JPY",
                    "units": 1000,
                    "price": 150.0,
                    "conversion_price": 0.0067,
                    "conversion_as_of": OPEN.isoformat(),
                }
            ],
        )
    )
    assert converted["broker_requests"] == 1
    assert abs(float(converted["details"]["existing_exposure"]) - 1005.0) < 1e-6


def test_failed_reconciliation_is_atomic_and_repeated() -> None:
    path = _seed("repeat-block")
    event = [{"id": "loss", "kind": "trade_pl", "amount": -200.0, "time": OPEN.isoformat()}]
    first = _run(broker_snapshot=_snap(snapshot_id="loss"), broker_events=event)
    second = _run(broker_snapshot=_snap(snapshot_id="loss"), broker_events=event)
    assert _blocked(first, "daily_realised_loss_limit")
    assert _blocked(second, "daily_realised_loss_limit")
    assert json.loads(path.read_text(encoding="utf-8"))["realised_by_day"]["2026-01-07"] == -200.0
    _clear()
    mixed = _seed("mixed")
    before = mixed.read_text(encoding="utf-8")
    mixed_result = _run(
        broker_snapshot=_snap(snapshot_id="mixed"),
        broker_events=[
            {"id": "ok", "kind": "trade_pl", "amount": -5.0, "time": OPEN.isoformat()},
            {"id": "fee", "kind": "fee", "amount": -1.0, "time": OPEN.isoformat()},
        ],
    )
    assert _blocked(mixed_result, "pnl_classification_unresolved")
    assert mixed.read_text(encoding="utf-8") == before
    _clear()
    absent = R26 / "states" / "absent.json"
    if absent.exists():
        absent.unlink()
    os.environ["RISK_STATE_PATH"] = str(absent)
    missing = _run(broker_snapshot=_snap())
    assert _blocked(missing, "risk_state_missing")
    assert not absent.exists()
    broken = _seed("broken")
    broken.write_text("{", encoding="utf-8")
    corrupt = _run(broker_snapshot=_snap())
    assert _blocked(corrupt, "risk_state_unreadable")
    assert broken.read_text(encoding="utf-8") == "{"
    _clear()
    locked = _seed("locked")
    lock = locked.with_suffix(locked.suffix + ".lock")
    handle = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_RDWR)
    try:
        contended = _run(broker_snapshot=_snap(snapshot_id="lock"))
        assert _blocked(contended, "risk_state_contention")
    finally:
        os.close(handle)
        os.remove(lock)
    _clear()
    readonly = _seed("readonly")
    before_mode = readonly.stat().st_mode
    before_text = readonly.read_text(encoding="utf-8")
    os.chmod(readonly, stat.S_IREAD)
    try:
        failed = _run(broker_snapshot=_snap(11000.0, snapshot_id="write-fail"))
        assert _blocked(failed, "durable_state_failed")
        assert readonly.read_text(encoding="utf-8") == before_text
    finally:
        os.chmod(readonly, before_mode)


def test_recovery_holds_still_precede_reconciliation() -> None:
    _seed("hold")
    note_unconfirmed_exposure("EUR_USD", "cid-filled")
    result = _run(broker_snapshot=_snap())
    assert result["blocked_by"] == "exposure_unconfirmed"
    assert result["broker_requests"] == 0
    assert "account_reconciliation" not in result["phases"]


def test_separate_processes_restore_durable_risk_state() -> None:
    driver = _load_driver()
    loss = R26 / "states" / "restart-loss.json"
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
    assert read["production_eligible"] is False

    draw = R26 / "states" / "restart-drawdown.json"
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

    exposed = R26 / "states" / "restart-exposure.json"
    driver.seed_state(exposed, peak=10000.0, baseline=1_000_000_000.0, realised=0.0)
    left = _spawn("persist", "exposure", exposed, "10000")
    _finish(left)
    right = _spawn("evaluate", "exposure", exposed, "10000")
    assert left.poll() is not None
    held = _finish(right)
    assert held["blocked_by"] == "total_exposure_limit"
    assert held["broker_requests"] == 0
    assert held["exposure_order_ids"] == ["pend-restart"]

    dedup = R26 / "states" / "restart-dedup.json"
    driver.seed_state(dedup, peak=10000.0, baseline=10000.0, realised=0.0)
    original = _spawn("persist", "duplicate", dedup, "10000")
    _finish(original)
    replay = _spawn("duplicate", "duplicate", dedup, "10000")
    assert original.poll() is not None
    replayed = _finish(replay)
    assert replayed["pid"] != original.pid
    assert replayed["realised"] == -50.0
    assert replayed["event_ids"] == ["trade-restart"]
    trace = {
        "daily_loss": {"writer": wrote, "reader": read},
        "drawdown": {"writer": peaked, "reader": declined},
        "exposure": held,
        "duplicate": replayed,
    }
    (R26 / "restart_trace.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")


def _spawn(role: str, scenario: str, state: Path, balance: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-B", str(DRIVER), role, "--scenario", scenario, "--state", str(state), "--balance", balance],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _finish(proc: subprocess.Popen) -> dict:
    stdout, stderr = proc.communicate(timeout=60)
    assert proc.returncode == 0 and stdout.strip(), stderr or stdout
    return json.loads(stdout)

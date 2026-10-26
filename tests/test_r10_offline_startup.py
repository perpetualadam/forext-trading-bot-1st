"""Offline startup integration. Real orchestration, fake external services.

Launch this file through data/research/adaptive_ensemble/r10/20_run_offline_tests.py
so the socket barrier and dotenv stub are installed before import.
"""

from __future__ import annotations

import atexit
import hashlib
import importlib.util
import inspect
import json
import os
import socket
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
R10 = ROOT / "data" / "research" / "adaptive_ensemble" / "r10"
SYMBOL = "EUR_USD"

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R10 / "synthetic_live_safety_state.json")

try:
    _probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
except RuntimeError as exc:
    if "NETWORK_BLOCKED" not in str(exc):
        raise
else:
    _probe.close()
    raise RuntimeError("R10_BLOCKED_TEST_ISOLATION")

from forex_bot.app import initialise_application, shutdown_application  # noqa: E402
from forex_bot import database as order_db  # noqa: E402
from forex_bot.database import (  # noqa: E402
    confirm_exposure_flat,
    exposure_entry_block_reason,
    fetch_exec_orders_open_for_recovery,
    order_status_proves_exposure_closed,
    reservation_status_block_reason,
    reset_order_intent_gate_for_tests,
)
from forex_bot.live_safety import live_order_auth_state  # noqa: E402
from forex_bot.orders import orders_by_client_id, reset_orders_for_tests  # noqa: E402
from forex_bot.positions import get_position, positions  # noqa: E402
from forex_bot.strategy_meta import strategies  # noqa: E402

_fake_spec = importlib.util.spec_from_file_location("r10_fakes", ROOT / "tests" / "r10_fakes.py")
_fake_mod = importlib.util.module_from_spec(_fake_spec)
assert _fake_spec is not None and _fake_spec.loader is not None
_fake_spec.loader.exec_module(_fake_mod)
OfflineServices = _fake_mod.OfflineServices

RESULTS: list[dict[str, object]] = []
SUCCESS_PHASES = [
    "created",
    "configuration_validated",
    "safety_defaults_verified",
    "persistence_initialized",
    "order_recovery_completed",
    "exposure_safety_evaluated",
    "broker_dependency_initialized",
    "market_data_dependency_initialized",
    "messaging_dependency_initialized",
    "health_dependencies_prepared",
    "offline_initialization_ready",
]
PRE_APP = "3ff01244ed217e85d211bec819a7ebff9c96fb0412c56e5a768792ab54b31ca1"
PROTECTED = {
    "forex_bot/bot_loop.py": "6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796",
    "forex_bot/database.py": "dfcab6b9b1b2c6f0d025666acc8878f17049eda11078406995d85280dae790b1",
    "forex_bot/orders.py": "fca93e8007d5f25413caf6b7e6493db0a27b4b81cffe78331d3321e9e76db1b4",
    "forex_bot/telegram_control.py": "d32b560306fe2f86cc7c8ddbb40aa42842f071bd88ea513d77f172a6a0fadf4c",
    "forex_bot/live_safety.py": "11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44",
    "forex_bot/strategy_meta.py": "492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d",
    "forex_bot/oanda_exec.py": "f4beb250d81852d8ee4f22af06ab33194c6b4ba1bf6f9b1a6b5d11d3b7b265c8",
    "requirements.txt": "45bc21ba5d8f336c0da5092024cee96103f0251d7c7f55e70056a7c55d194b0a",
    "requirements-dev.txt": "0562a6853549077197defb3cd8515521b843a041f2a735723ee2903790e3eef5",
    "Dockerfile": "4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad",
    ".dockerignore": "5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd",
    "docker-compose.yml": "f0a374774c35b4c63dce23a837572886d1d53331fec388044bc5887367980179",
}


def _sha(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def _dump_results() -> None:
    R10.mkdir(parents=True, exist_ok=True)
    (R10 / "10_integration_test_results.json").write_text(
        json.dumps(RESULTS, indent=2),
        encoding="utf-8",
    )


atexit.register(_dump_results)


def setup_function() -> None:
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(R10 / "synthetic_live_safety_state.json")
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    positions.clear()


def drive(coro):
    try:
        while True:
            coro.send(None)
    except StopIteration as stop:
        return stop.value


def row(status: str, client_order_id: str = "c1", **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "client_order_id": client_order_id,
        "symbol": SYMBOL,
        "side": "BUY",
        "units": 1.0,
        "status": status,
        "filled_units": 1.0 if status == "FILLED" else 0.0,
        "metadata": {},
    }
    payload.update(extra)
    return payload


def start(services: OfflineServices):
    try:
        report = drive(initialise_application(services.ports()))
    except Exception as exc:
        return getattr(exc, "startup_report", None), exc
    return report, None


def record(
    test_id: str,
    function: str,
    application_function: str,
    fakes: str,
    expected: str,
    actual: str,
    status: str,
    *,
    seam: bool,
    evidence: str,
) -> None:
    RESULTS.append(
        {
            "test_id": test_id,
            "test_function": function,
            "application_function": application_function,
            "fake_dependencies": fakes,
            "expected": expected,
            "actual": actual,
            "status": status,
            "startup_seam_executed": seam,
            "real_launcher_executed": False,
            "real_broker_used": False,
            "postgresql_used": False,
            "evidence": evidence,
        }
    )


def case(test_id, function, application_function, fakes, expected, seam, evidence, body):
    actual = expected
    status = "PASS"
    try:
        returned = body()
        if returned is not None:
            actual = returned
    except Exception as exc:
        status = "FAIL"
        actual = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        record(
            test_id,
            function,
            application_function,
            fakes,
            expected,
            actual,
            status,
            seam=seam,
            evidence=evidence,
        )


def _ready(report, exc) -> None:
    assert exc is None and report is not None
    assert report.ok is True
    assert report.offline_ready is True
    assert report.trading_ready is False
    assert report.trading_loop_started is False
    assert report.phases == SUCCESS_PHASES
    assert "running" not in report.phases


def _closed(report, exc, error_name: str) -> None:
    assert exc is not None and report is not None
    assert report.ok is False
    assert report.offline_ready is False
    assert report.trading_ready is False
    assert report.trading_loop_started is False
    assert "offline_initialization_ready" not in report.phases
    assert report.error == error_name
    assert order_db._pg_conn is None


def test_i01_offline_initialization_succeeds() -> None:
    def body() -> str:
        services = OfflineServices()
        report, exc = start(services)
        _ready(report, exc)
        assert services.rejected == []
        assert services.messages == []
        assert order_db._pg_conn is None
        shutdown_application(services.ports(), report)
        assert services.open == []
        return "offline_initialization_ready trading_ready=False"

    case(
        "I01",
        "test_i01_offline_initialization_succeeds",
        "initialise_application",
        "persistence,recovery,broker,market,messaging,health,scheduler",
        "offline ready, trading not ready",
        True,
        "phases end at offline_initialization_ready",
        body,
    )


def test_i02_phases_follow_startup_order() -> None:
    def body() -> str:
        report, exc = start(OfflineServices())
        _ready(report, exc)
        return ">".join(report.phases)

    case(
        "I02",
        "test_i02_phases_follow_startup_order",
        "initialise_application",
        "full offline bundle",
        "created through offline_initialization_ready",
        True,
        "phase list equals the orchestrator order",
        body,
    )


def test_i03_configuration_is_validated() -> None:
    def body() -> str:
        services = OfflineServices()
        report, exc = start(services)
        _ready(report, exc)
        assert "validate_config" in services.calls
        assert "configuration_validated" in report.phases
        return "configuration_validated"

    case(
        "I03",
        "test_i03_configuration_is_validated",
        "initialise_application",
        "validate_config",
        "configuration phase completed",
        True,
        "fake config accepted",
        body,
    )


def test_i04_live_order_permission_stays_blocked() -> None:
    def body() -> str:
        report, exc = start(OfflineServices())
        _ready(report, exc)
        assert live_order_auth_state() == "BLOCKED"
        return live_order_auth_state()

    case(
        "I04",
        "test_i04_live_order_permission_stays_blocked",
        "initialise_fail_closed",
        "verify_safety",
        "BLOCKED",
        True,
        "effective auth remains BLOCKED",
        body,
    )


def test_i05_strategies_remain_inactive() -> None:
    def body() -> str:
        report, exc = start(OfflineServices())
        _ready(report, exc)
        assert strategies
        assert all(item.active is False for item in strategies.values())
        return "all_inactive"

    case(
        "I05",
        "test_i05_strategies_remain_inactive",
        "initialise_fail_closed",
        "verify_safety",
        "strategies inactive",
        True,
        "strategy objects stay inactive",
        body,
    )


def test_i06_no_real_broker_is_constructed() -> None:
    def body() -> str:
        report, exc = start(OfflineServices())
        _ready(report, exc)
        assert "forex_bot.oanda_client" not in sys.modules
        assert "oandapyV20" not in sys.modules
        return "oanda_modules_absent"

    case(
        "I06",
        "test_i06_no_real_broker_is_constructed",
        "initialise_application",
        "fake broker",
        "no OANDA module",
        True,
        "offline path does not import the broker SDK",
        body,
    )


def test_i07_no_real_database_is_constructed() -> None:
    def body() -> str:
        report, exc = start(OfflineServices())
        _ready(report, exc)
        assert order_db._pg_conn is None
        return "pg_conn_none"

    case(
        "I07",
        "test_i07_no_real_database_is_constructed",
        "initialise_application",
        "fake persistence",
        "no PostgreSQL connection",
        True,
        "_pg_conn stays None",
        body,
    )


def test_i08_no_real_messaging_connection() -> None:
    def body() -> str:
        services = OfflineServices()
        report, exc = start(services)
        _ready(report, exc)
        assert services.messages == []
        return "no_outgoing_message"

    case(
        "I08",
        "test_i08_no_real_messaging_connection",
        "initialise_application",
        "fake messaging",
        "no message sent",
        True,
        "messaging fake records no send",
        body,
    )


def test_i09_no_trading_loop_scheduling() -> None:
    def body() -> str:
        services = OfflineServices()
        report, exc = start(services)
        _ready(report, exc)
        assert services.schedule_status == "recorded_not_started"
        assert "schedule" in services.calls
        assert report.trading_loop_started is False
        assert "forex_bot.bot_loop" not in sys.modules
        return "recorded_not_started"

    case(
        "I09",
        "test_i09_no_trading_loop_scheduling",
        "initialise_application",
        "fake scheduler",
        "schedule recorded, loop not started",
        True,
        "run_bot module was not imported",
        body,
    )


def test_i10_offline_ready_is_not_trading_ready() -> None:
    def body() -> str:
        report, exc = start(OfflineServices())
        _ready(report, exc)
        return f"offline={report.offline_ready} trading={report.trading_ready}"

    case(
        "I10",
        "test_i10_offline_ready_is_not_trading_ready",
        "initialise_application",
        "full offline bundle",
        "offline true, trading false",
        True,
        "ready phase is offline_initialization_ready",
        body,
    )


def test_i11_empty_confirmed_recovery() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = []
        report, exc = start(services)
        _ready(report, exc)
        assert report.exposure[SYMBOL] is None
        assert orders_by_client_id == {}
        return "empty_confirmed"

    case(
        "I11",
        "test_i11_empty_confirmed_recovery",
        "ingest_recovery_snapshot",
        "empty readable rows",
        "no exposure block",
        True,
        "E01 empty book",
        body,
    )


def test_i12_pending_recovery() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("PENDING")]
        report, exc = start(services)
        _ready(report, exc)
        assert report.exposure[SYMBOL] == "active_reservation"
        return report.exposure[SYMBOL]

    case(
        "I12",
        "test_i12_pending_recovery",
        "ingest_recovery_snapshot",
        "PENDING row",
        "active_reservation",
        True,
        "E02",
        body,
    )


def test_i13_partial_recovery() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("PARTIAL")]
        report, exc = start(services)
        _ready(report, exc)
        assert report.exposure[SYMBOL] == "active_reservation"
        return report.exposure[SYMBOL]

    case(
        "I13",
        "test_i13_partial_recovery",
        "ingest_recovery_snapshot",
        "PARTIAL row",
        "active_reservation",
        True,
        "E03",
        body,
    )


def test_i14_unresolved_recovery() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("UNRESOLVED")]
        report, exc = start(services)
        _ready(report, exc)
        assert report.exposure[SYMBOL] == "unresolved_intent"
        return report.exposure[SYMBOL]

    case(
        "I14",
        "test_i14_unresolved_recovery",
        "ingest_recovery_snapshot",
        "UNRESOLVED row",
        "unresolved_intent",
        True,
        "E04",
        body,
    )


def test_i15_filled_with_unconfirmed_exposure() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("FILLED", metadata={"exposure_safety": "UNCONFIRMED"})]
        report, exc = start(services)
        _ready(report, exc)
        assert report.exposure[SYMBOL] == "exposure_unconfirmed"
        assert get_position(SYMBOL) is None
        return report.exposure[SYMBOL]

    case(
        "I15",
        "test_i15_filled_with_unconfirmed_exposure",
        "ingest_recovery_snapshot",
        "FILLED UNCONFIRMED row",
        "exposure_unconfirmed",
        True,
        "E05 empty position slot is not flat proof",
        body,
    )


def test_i16_filled_without_marker() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("FILLED")]
        report, exc = start(services)
        _ready(report, exc)
        assert report.exposure[SYMBOL] == "exposure_unconfirmed"
        assert report.historical_filled_gap is False
        return report.exposure[SYMBOL]

    case(
        "I16",
        "test_i16_filled_without_marker",
        "ingest_recovery_snapshot",
        "FILLED row without marker",
        "exposure_unconfirmed",
        True,
        "E06 supplied FILLED row still blocks after the source query repair",
        body,
    )


def test_i17_corrupt_recovery_state() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("NOT_A_STATUS")]
        report, exc = start(services)
        _closed(report, exc, "OrderRecoveryUnreadable")
        return report.error

    case(
        "I17",
        "test_i17_corrupt_recovery_state",
        "ingest_recovery_snapshot",
        "corrupt status",
        "fail closed",
        True,
        "E07",
        body,
    )


def test_i18_failed_recovery_read() -> None:
    def body() -> str:
        services = OfflineServices()
        services.use_provider = True
        services.fail = "recovery"
        report, exc = start(services)
        _closed(report, exc, "RuntimeError")
        return report.error

    case(
        "I18",
        "test_i18_failed_recovery_read",
        "initialise_application",
        "recovery provider",
        "fail closed",
        True,
        "E09 provider exception",
        body,
    )


def test_i19_conflicting_position_state() -> None:
    def body() -> str:
        from forex_bot.orders import record_synthetic_fill_position

        services = OfflineServices()
        services.rows = [row("FILLED", metadata={"exposure_safety": "UNCONFIRMED"})]
        report, exc = start(services)
        _ready(report, exc)
        first = record_synthetic_fill_position(
            symbol=SYMBOL,
            client_order_id="c1",
            direction="BUY",
            units=1.0,
            price=1.2,
        )
        second = record_synthetic_fill_position(
            symbol=SYMBOL,
            client_order_id="c1",
            direction="SELL",
            units=2.0,
            price=1.2,
        )
        assert first == "recorded"
        assert second == "conflict"
        assert report.exposure[SYMBOL] == "exposure_unconfirmed"
        assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"
        return second

    case(
        "I19",
        "test_i19_conflicting_position_state",
        "record_synthetic_fill_position",
        "FILLED row plus conflicting synthetic position",
        "conflict",
        True,
        "E14 conflict does not replace the position",
        body,
    )


def test_i20_repeated_recovery_is_idempotent() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("PENDING", client_order_id="same")]
        services.lifecycle["allow_repeat"] = True
        first, first_exc = start(services)
        second, second_exc = start(services)
        _ready(first, first_exc)
        _ready(second, second_exc)
        assert len(orders_by_client_id) == 1
        return str(len(orders_by_client_id))

    case(
        "I20",
        "test_i20_repeated_recovery_is_idempotent",
        "ingest_recovery_snapshot",
        "same PENDING row twice",
        "one order",
        True,
        "E19 duplicate client id is not registered twice",
        body,
    )


def test_i21_missing_position_record() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("FILLED", metadata={"exposure_safety": "UNCONFIRMED"})]
        report, exc = start(services)
        _ready(report, exc)
        assert get_position(SYMBOL) is None
        assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"
        return "missing_position_hold"

    case(
        "I21",
        "test_i21_missing_position_record",
        "exposure_entry_block_reason",
        "FILLED row and empty position book",
        "hold remains",
        True,
        "E13",
        body,
    )


def test_i22_unknown_broker_exposure() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("FILLED")]
        services.market_snapshot["exposure"] = "unknown"
        report, exc = start(services)
        _ready(report, exc)
        assert services.market_snapshot["exposure"] == "unknown"
        assert report.exposure[SYMBOL] == "exposure_unconfirmed"
        assert confirm_exposure_flat(SYMBOL, evidence="unknown") is False
        return "unknown_exposure_hold"

    case(
        "I22",
        "test_i22_unknown_broker_exposure",
        "confirm_exposure_flat",
        "fake market snapshot exposure=unknown",
        "hold remains",
        True,
        "E17 unknown token is not flat proof",
        body,
    )


def test_i23_historical_filled_row() -> None:
    def body() -> str:
        from forex_bot.database import RECOVERY_SELECTION_SQL

        source = inspect.getsource(fetch_exec_orders_open_for_recovery)
        assert "RECOVERY_SELECTION_SQL" in source
        assert "status = 'FILLED'" in RECOVERY_SELECTION_SQL
        assert "CONFIRMED_FLAT" in RECOVERY_SELECTION_SQL
        services = OfflineServices()
        services.rows = [row("FILLED")]
        report, exc = start(services)
        _ready(report, exc)
        assert report.exposure[SYMBOL] == "exposure_unconfirmed"
        assert report.historical_filled_gap is False
        return "historical_filled_selected"

    case(
        "I23",
        "test_i23_historical_filled_row",
        "fetch_exec_orders_open_for_recovery",
        "source inspection plus supplied FILLED snapshot",
        "legacy FILLED remains blocked",
        True,
        "E16 source query now keeps an unmarked FILLED row; PostgreSQL was not executed",
        body,
    )


def test_i24_reconciliation_unavailable() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("PENDING")]
        services.reconciliation_unavailable = True
        report, exc = start(services)
        _ready(report, exc)
        assert report.reconciliation == "ReconciliationUnavailable"
        assert report.exposure[SYMBOL] == "active_reservation"
        return report.reconciliation

    case(
        "I24",
        "test_i24_reconciliation_unavailable",
        "initialise_application",
        "market data raises ReconciliationUnavailable",
        "hold kept",
        True,
        "E15 reconciliation failure does not clear the reservation",
        body,
    )


def test_i25_unresolved_order_prevents_false_flat() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("UNRESOLVED")]
        report, exc = start(services)
        _ready(report, exc)
        assert confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False
        assert exposure_entry_block_reason(SYMBOL) == "unresolved_intent"
        return "flat_token_refused"

    case(
        "I25",
        "test_i25_unresolved_order_prevents_false_flat",
        "confirm_exposure_flat",
        "UNRESOLVED row",
        "flat token refused",
        True,
        "E18",
        body,
    )


def test_i26_invalid_configuration() -> None:
    def body() -> str:
        services = OfflineServices()
        services.config_valid = False
        report, exc = start(services)
        _closed(report, exc, "ValueError")
        assert "persistence" not in services.closed
        return report.error

    case(
        "I26",
        "test_i26_invalid_configuration",
        "initialise_application",
        "invalid fake configuration",
        "fail closed",
        True,
        "F01",
        body,
    )


def test_i27_missing_dependency() -> None:
    def body() -> str:
        services = OfflineServices()
        services.missing = "broker"
        report, exc = start(services)
        _closed(report, exc, "RuntimeError")
        assert "persistence" in services.closed
        return report.error

    case(
        "I27",
        "test_i27_missing_dependency",
        "initialise_application",
        "broker missing",
        "fail closed",
        True,
        "F02",
        body,
    )


def test_i28_persistence_initialization_fails() -> None:
    def body() -> str:
        services = OfflineServices()
        services.fail = "persistence"
        report, exc = start(services)
        _closed(report, exc, "RuntimeError")
        assert services.open == []
        return report.error

    case(
        "I28",
        "test_i28_persistence_initialization_fails",
        "initialise_application",
        "persistence failure",
        "fail closed",
        True,
        "F03",
        body,
    )


def test_i29_recovery_provider_fails() -> None:
    def body() -> str:
        services = OfflineServices()
        services.use_provider = True
        services.fail = "recovery"
        report, exc = start(services)
        _closed(report, exc, "RuntimeError")
        assert "persistence" in services.closed
        return report.error

    case(
        "I29",
        "test_i29_recovery_provider_fails",
        "initialise_application",
        "recovery provider",
        "fail closed",
        True,
        "F04",
        body,
    )


def test_i30_broker_dependency_fails() -> None:
    def body() -> str:
        services = OfflineServices()
        services.fail = "broker"
        report, exc = start(services)
        _closed(report, exc, "RuntimeError")
        assert services.closed == ["persistence"]
        return report.error

    case(
        "I30",
        "test_i30_broker_dependency_fails",
        "initialise_application",
        "broker failure",
        "fail closed",
        True,
        "F06",
        body,
    )


def test_i31_market_data_dependency_fails() -> None:
    def body() -> str:
        services = OfflineServices()
        services.fail = "market_data"
        report, exc = start(services)
        _closed(report, exc, "RuntimeError")
        assert services.closed == ["broker", "persistence"]
        return report.error

    case(
        "I31",
        "test_i31_market_data_dependency_fails",
        "initialise_application",
        "market-data failure",
        "fail closed",
        True,
        "F07",
        body,
    )


def test_i32_messaging_dependency_fails() -> None:
    def body() -> str:
        services = OfflineServices()
        services.fail = "messaging"
        report, exc = start(services)
        _closed(report, exc, "RuntimeError")
        return report.error

    case(
        "I32",
        "test_i32_messaging_dependency_fails",
        "initialise_application",
        "messaging failure",
        "fail closed",
        True,
        "F08",
        body,
    )


def test_i33_health_dependency_fails() -> None:
    def body() -> str:
        services = OfflineServices()
        services.fail = "health"
        report, exc = start(services)
        _closed(report, exc, "RuntimeError")
        return report.error

    case(
        "I33",
        "test_i33_health_dependency_fails",
        "initialise_application",
        "health failure",
        "fail closed",
        True,
        "F09",
        body,
    )


def test_i34_scheduler_rejects_a_task() -> None:
    def body() -> str:
        services = OfflineServices()
        services.fail = "schedule"
        report, exc = start(services)
        _closed(report, exc, "RuntimeError")
        assert "scheduler" not in services.open
        assert report.trading_loop_started is False
        return report.error

    case(
        "I34",
        "test_i34_scheduler_rejects_a_task",
        "initialise_application",
        "scheduler refusal",
        "fail closed",
        True,
        "F10",
        body,
    )


def test_i35_dependency_raises_unexpectedly() -> None:
    def body() -> str:
        services = OfflineServices()
        services.fail = "health"
        report, exc = start(services)
        _closed(report, exc, "RuntimeError")
        assert "run_bot" not in services.calls
        return report.error

    case(
        "I35",
        "test_i35_dependency_raises_unexpectedly",
        "initialise_application",
        "unexpected health exception",
        "fail closed",
        True,
        "F15",
        body,
    )


def test_i36_duplicate_initialization() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("PENDING", client_order_id="once")]
        first, first_exc = start(services)
        _ready(first, first_exc)
        second, second_exc = start(services)
        _closed(second, second_exc, "StartupSafetyAbort")
        assert len(orders_by_client_id) == 1
        return "duplicate_refused"

    case(
        "I36",
        "test_i36_duplicate_initialization",
        "initialise_application",
        "same lifecycle",
        "second call refused",
        True,
        "F13",
        body,
    )


def test_i37_initialization_interrupted() -> None:
    def body() -> str:
        services = OfflineServices()
        services.interrupt = "broker"
        report, exc = start(services)
        _closed(report, exc, "RuntimeError")
        assert "persistence" in services.closed
        return "interrupted"

    case(
        "I37",
        "test_i37_initialization_interrupted",
        "initialise_application",
        "broker interrupt",
        "fail closed",
        True,
        "F12",
        body,
    )


def test_i38_no_false_ready_after_failure() -> None:
    def body() -> str:
        services = OfflineServices()
        services.readable = False
        services.rows = [row("PENDING")]
        report, exc = start(services)
        _closed(report, exc, "OrderRecoveryUnreadable")
        assert report.offline_ready is False
        return "not_ready"

    case(
        "I38",
        "test_i38_no_false_ready_after_failure",
        "ingest_recovery_snapshot",
        "unreadable recovery",
        "not ready",
        True,
        "F05 and F20 readiness stays false",
        body,
    )


def test_i39_cleanup_after_partial_startup() -> None:
    def body() -> str:
        services = OfflineServices()
        services.fail = "messaging"
        report, exc = start(services)
        _closed(report, exc, "RuntimeError")
        assert services.open == []
        assert services.closed == ["market_data", "broker", "persistence"]
        return ">".join(services.closed)

    case(
        "I39",
        "test_i39_cleanup_after_partial_startup",
        "initialise_application",
        "messaging failure after earlier fakes opened",
        "opened fakes closed in reverse",
        True,
        "G04",
        body,
    )


def test_i40_cleanup_error_is_visible() -> None:
    def body() -> str:
        services = OfflineServices()
        services.cleanup_error = "close_failed:persistence"
        report, exc = start(services)
        _ready(report, exc)
        shutdown_application(services.ports(), report)
        assert "close_failed:persistence" in report.cleanup_errors
        assert services.open == []
        return "close_failed:persistence"

    case(
        "I40",
        "test_i40_cleanup_error_is_visible",
        "shutdown_application",
        "cleanup error string",
        "error visible",
        True,
        "F11 and G10",
        body,
    )


def test_i41_clean_shutdown() -> None:
    def body() -> str:
        services = OfflineServices()
        report, exc = start(services)
        _ready(report, exc)
        shutdown_application(services.ports(), report)
        assert services.closed == [
            "scheduler",
            "health",
            "messaging",
            "market_data",
            "broker",
            "persistence",
        ]
        assert services.open == []
        assert report.offline_ready is False
        return ">".join(services.closed)

    case(
        "I41",
        "test_i41_clean_shutdown",
        "shutdown_application",
        "full offline bundle",
        "reverse close order",
        True,
        "G01 G02",
        body,
    )


def test_i42_repeated_shutdown() -> None:
    def body() -> str:
        services = OfflineServices()
        report, exc = start(services)
        _ready(report, exc)
        shutdown_application(services.ports(), report)
        shutdown_application(services.ports(), report)
        assert services.open == []
        assert report.trading_ready is False
        return "second_shutdown_safe"

    case(
        "I42",
        "test_i42_repeated_shutdown",
        "shutdown_application",
        "full offline bundle",
        "idempotent",
        True,
        "G03",
        body,
    )


def test_i43_no_pending_trading_task() -> None:
    def body() -> str:
        services = OfflineServices()
        report, exc = start(services)
        _ready(report, exc)
        shutdown_application(services.ports(), report)
        assert report.trading_loop_started is False
        assert "forex_bot.bot_loop" not in sys.modules
        return "no_trading_task"

    case(
        "I43",
        "test_i43_no_pending_trading_task",
        "shutdown_application",
        "fake scheduler",
        "loop not started",
        True,
        "G05",
        body,
    )


def test_i44_no_open_fake_database_resources() -> None:
    def body() -> str:
        services = OfflineServices()
        report, exc = start(services)
        shutdown_application(services.ports(), report)
        assert "persistence" not in services.open
        assert order_db._pg_conn is None
        return "persistence_closed"

    case(
        "I44",
        "test_i44_no_open_fake_database_resources",
        "shutdown_application",
        "fake persistence",
        "closed",
        True,
        "G07",
        body,
    )


def test_i45_no_open_fake_broker_resources() -> None:
    def body() -> str:
        services = OfflineServices()
        report, exc = start(services)
        shutdown_application(services.ports(), report)
        assert "broker" not in services.open
        with pytest.raises(RuntimeError, match="rejects order submission"):
            services.submit_order()
        return "broker_closed"

    case(
        "I45",
        "test_i45_no_open_fake_broker_resources",
        "shutdown_application",
        "fake broker",
        "closed and submission rejected",
        True,
        "G06",
        body,
    )


def test_i46_no_open_fake_messaging_resources() -> None:
    def body() -> str:
        services = OfflineServices()
        report, exc = start(services)
        shutdown_application(services.ports(), report)
        assert "messaging" not in services.open
        with pytest.raises(RuntimeError, match="does not send"):
            services.send_message("hello")
        assert services.messages == ["hello"]
        return "messaging_closed"

    case(
        "I46",
        "test_i46_no_open_fake_messaging_resources",
        "shutdown_application",
        "fake messaging",
        "closed and send rejected",
        True,
        "G08",
        body,
    )


def test_i47_no_surviving_background_worker() -> None:
    def body() -> str:
        services = OfflineServices()
        report, exc = start(services)
        shutdown_application(services.ports(), report)
        assert services.open == []
        assert "scheduler" in services.closed
        return "no_worker"

    case(
        "I47",
        "test_i47_no_surviving_background_worker",
        "shutdown_application",
        "fake scheduler",
        "no open worker",
        True,
        "G09",
        body,
    )


def test_i48_no_automatic_restart() -> None:
    def body() -> str:
        services = OfflineServices()
        report, exc = start(services)
        shutdown_application(services.ports(), report)
        again, again_exc = start(services)
        _closed(again, again_exc, "StartupSafetyAbort")
        assert services.calls.count("schedule") == 1
        return "restart_refused"

    case(
        "I48",
        "test_i48_no_automatic_restart",
        "initialise_application",
        "lifecycle stopped",
        "no restart",
        True,
        "F14",
        body,
    )


def test_i49_pending_duplicate_block() -> None:
    def body() -> str:
        from forex_bot.orders import try_begin_order_submission

        services = OfflineServices()
        services.rows = [row("PENDING", client_order_id="held")]
        report, exc = start(services)
        _ready(report, exc)
        assert reservation_status_block_reason("PENDING") == "active_reservation"
        allowed = try_begin_order_submission(
            client_order_id="new",
            symbol=SYMBOL,
            direction="BUY",
            units=1.0,
        )
        assert allowed is False
        assert services.rejected == []
        return "blocked"

    case(
        "I49",
        "test_i49_pending_duplicate_block",
        "try_begin_order_submission",
        "PENDING recovery",
        "new client id refused",
        True,
        "R.8 pending block",
        body,
    )


def test_i50_partial_duplicate_block() -> None:
    def body() -> str:
        from forex_bot.orders import try_begin_order_submission

        services = OfflineServices()
        services.rows = [row("PARTIAL", client_order_id="part")]
        report, exc = start(services)
        _ready(report, exc)
        allowed = try_begin_order_submission(
            client_order_id="new",
            symbol=SYMBOL,
            direction="BUY",
            units=1.0,
        )
        assert allowed is False
        return "blocked"

    case(
        "I50",
        "test_i50_partial_duplicate_block",
        "try_begin_order_submission",
        "PARTIAL recovery",
        "new client id refused",
        True,
        "R.8 partial block",
        body,
    )


def test_i51_unresolved_duplicate_block() -> None:
    def body() -> str:
        from forex_bot.orders import try_begin_order_submission

        services = OfflineServices()
        services.rows = [row("UNRESOLVED", client_order_id="amb")]
        report, exc = start(services)
        _ready(report, exc)
        allowed = try_begin_order_submission(
            client_order_id="new",
            symbol=SYMBOL,
            direction="BUY",
            units=1.0,
        )
        assert allowed is False
        return "blocked"

    case(
        "I51",
        "test_i51_unresolved_duplicate_block",
        "try_begin_order_submission",
        "UNRESOLVED recovery",
        "new client id refused",
        True,
        "R.8 unresolved block",
        body,
    )


def test_i52_filled_exposure_hold() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("FILLED", metadata={"exposure_safety": "UNCONFIRMED"})]
        report, exc = start(services)
        _ready(report, exc)
        assert order_status_proves_exposure_closed("FILLED") is False
        assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"
        return "exposure_unconfirmed"

    case(
        "I52",
        "test_i52_filled_exposure_hold",
        "exposure_entry_block_reason",
        "FILLED UNCONFIRMED",
        "hold remains",
        True,
        "R.9 fill is not flat proof",
        body,
    )


def test_i53_missing_position_hold() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("FILLED")]
        report, exc = start(services)
        _ready(report, exc)
        assert get_position(SYMBOL) is None
        assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"
        return "hold_without_position"

    case(
        "I53",
        "test_i53_missing_position_hold",
        "exposure_entry_block_reason",
        "FILLED without a position object",
        "hold remains",
        True,
        "R.9 missing position",
        body,
    )


def test_i54_invalid_direction_gate_preserved() -> None:
    def body() -> str:
        from forex_bot.bot_loop import direction_action_gate

        called: list[str] = []
        result = direction_action_gate("HOLD", called.append, called.append, called.append)
        assert result is None
        assert called == []
        return "direction_blocked"

    case(
        "I54",
        "test_i54_invalid_direction_gate_preserved",
        "direction_action_gate",
        "none",
        "sender not called",
        False,
        "invalid direction stops before dispatch",
        body,
    )


def test_i55_inactive_strategy_gate_preserved() -> None:
    def body() -> str:
        from forex_bot.bot_loop import strategy_entry_block_reason

        reason = strategy_entry_block_reason(
            "sma_cross",
            active=False,
            authorised_for_live=False,
            safety_initialised=True,
            known_strategy=True,
        )
        assert reason == "STRATEGY_INACTIVE"
        assert all(item.active is False for item in strategies.values())
        return reason

    case(
        "I55",
        "test_i55_inactive_strategy_gate_preserved",
        "strategy_entry_block_reason",
        "none",
        "STRATEGY_INACTIVE",
        False,
        "inactive strategy stops before sizing",
        body,
    )


def test_i56_live_authorisation_gate_preserved() -> None:
    def body() -> str:
        from forex_bot.bot_loop import strategy_entry_block_reason

        report, exc = start(OfflineServices())
        _ready(report, exc)
        assert live_order_auth_state() == "BLOCKED"
        reason = strategy_entry_block_reason(
            "sma_cross",
            active=True,
            authorised_for_live=False,
            safety_initialised=True,
            known_strategy=True,
        )
        assert reason == "STRATEGY_NOT_AUTHORISED"
        return reason

    case(
        "I56",
        "test_i56_live_authorisation_gate_preserved",
        "strategy_entry_block_reason",
        "verify_safety",
        "STRATEGY_NOT_AUTHORISED",
        True,
        "live authorisation stays blocked",
        body,
    )


def test_i57_no_broker_dispatch() -> None:
    def body() -> str:
        services = OfflineServices()
        report, exc = start(services)
        _ready(report, exc)
        assert services.rejected == []
        with pytest.raises(RuntimeError, match="rejects position closing"):
            services.close_position()
        return "no_dispatch"

    case(
        "I57",
        "test_i57_no_broker_dispatch",
        "initialise_application",
        "fake broker",
        "no order and close rejected",
        True,
        "startup did not submit an order",
        body,
    )


def test_i58_no_postgresql_connection() -> None:
    def body() -> str:
        report, exc = start(OfflineServices())
        _ready(report, exc)
        assert order_db._pg_conn is None
        return "no_connection"

    case(
        "I58",
        "test_i58_no_postgresql_connection",
        "initialise_application",
        "fake persistence",
        "connection absent",
        True,
        "_pg_conn is None after startup",
        body,
    )


def test_i59_no_external_network() -> None:
    def body() -> str:
        with pytest.raises(RuntimeError, match="NETWORK_BLOCKED"):
            socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with pytest.raises(RuntimeError, match="NETWORK_BLOCKED"):
            socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        return "network_blocked"

    case(
        "I59",
        "test_i59_no_external_network",
        "none",
        "socket barrier",
        "blocked",
        False,
        "AF_INET and AF_INET6 constructors raise",
        body,
    )


def test_i60_no_dns_resolution() -> None:
    def body() -> str:
        with pytest.raises(RuntimeError, match="DNS_BLOCKED"):
            socket.getaddrinfo("example.com", 80)
        return "dns_blocked"

    case(
        "I60",
        "test_i60_no_dns_resolution",
        "none",
        "dns barrier",
        "blocked",
        False,
        "getaddrinfo raises",
        body,
    )


def test_i61_no_application_launcher() -> None:
    def body() -> str:
        assert "main" not in sys.modules
        launcher = (ROOT / "main.py").read_text(encoding="utf-8")
        assert "uvicorn.run" in launcher
        return "launcher_not_imported"

    case(
        "I61",
        "test_i61_no_application_launcher",
        "none",
        "none",
        "main not imported",
        False,
        "source still contains the launcher; this process did not import it",
        body,
    )


def test_i62_no_run_bot_execution() -> None:
    def body() -> str:
        called: list[str] = []
        trap = types.ModuleType("forex_bot.bot_loop")

        def run_bot():
            called.append("run_bot")
            raise AssertionError("run_bot executed")

        trap.run_bot = run_bot
        sys.modules["forex_bot.bot_loop"] = trap
        try:
            report, exc = start(OfflineServices())
            _ready(report, exc)
            assert called == []
        finally:
            sys.modules.pop("forex_bot.bot_loop", None)
            import forex_bot

            if hasattr(forex_bot, "bot_loop"):
                delattr(forex_bot, "bot_loop")
        return "run_bot_not_called"

    case(
        "I62",
        "test_i62_no_run_bot_execution",
        "initialise_application",
        "trapped run_bot",
        "not called",
        True,
        "offline scheduler does not import run_bot",
        body,
    )


def test_i63_no_source_changes_outside_scope() -> None:
    def body() -> str:
        for relative, expected in PROTECTED.items():
            assert _sha(relative) == expected, relative
        assert _sha("forex_bot/app.py") != PRE_APP
        return "protected_hashes_match"

    case(
        "I63",
        "test_i63_no_source_changes_outside_scope",
        "none",
        "none",
        "protected files unchanged",
        False,
        "app.py is the approved startup seam",
        body,
    )


def test_i64_postgresql_not_evaluated() -> None:
    record(
        "I64",
        "test_i64_postgresql_not_evaluated",
        "none",
        "none",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
        seam=False,
        evidence="PostgreSQL was not started",
    )
    pytest.skip("NOT_EVALUATED")


def test_i65_broker_reconciliation_not_evaluated() -> None:
    record(
        "I65",
        "test_i65_broker_reconciliation_not_evaluated",
        "none",
        "none",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
        seam=False,
        evidence="no broker reconciliation",
    )
    pytest.skip("NOT_EVALUATED")


def test_i66_production_startup_not_evaluated() -> None:
    record(
        "I66",
        "test_i66_production_startup_not_evaluated",
        "lifespan",
        "none",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
        seam=False,
        evidence="production lifespan was not entered",
    )
    pytest.skip("NOT_EVALUATED")


def test_i67_actual_position_recovery_not_evaluated() -> None:
    record(
        "I67",
        "test_i67_actual_position_recovery_not_evaluated",
        "none",
        "none",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
        seam=False,
        evidence="no broker position query",
    )
    pytest.skip("NOT_EVALUATED")


def test_i68_trading_loop_not_evaluated() -> None:
    record(
        "I68",
        "test_i68_trading_loop_not_evaluated",
        "run_bot",
        "none",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
        seam=False,
        evidence="run_bot was not executed",
    )
    pytest.skip("NOT_EVALUATED")


def test_e08_missing_required_order_fields() -> None:
    services = OfflineServices()
    services.rows = [{"status": "PENDING"}]
    report, exc = start(services)
    _closed(report, exc, "OrderRecoveryUnreadable")


def test_e10_incomplete_recovery_data() -> None:
    services = OfflineServices()
    services.use_provider = True
    services.fail = "recovery_incomplete"
    report, exc = start(services)
    _closed(report, exc, "OrderRecoveryUnreadable")


def test_e11_duplicate_client_order_ids() -> None:
    services = OfflineServices()
    services.rows = [row("PENDING", "dup"), row("PENDING", "dup")]
    report, exc = start(services)
    _ready(report, exc)
    assert len(orders_by_client_id) == 1


def test_e12_multiple_active_orders_for_one_instrument() -> None:
    services = OfflineServices()
    services.rows = [row("PENDING", "a"), row("PARTIAL", "b")]
    report, exc = start(services)
    _ready(report, exc)
    assert len(orders_by_client_id) == 2
    assert report.exposure[SYMBOL] == "active_reservation"


def test_f16_unexpected_schedule_result() -> None:
    services = OfflineServices()
    services.schedule_awaitable = True
    services.schedule_status = "started"
    report, exc = start(services)
    _closed(report, exc, "StartupSafetyAbort")
    assert report.trading_loop_started is False


def test_f19_unexpected_application_state() -> None:
    services = OfflineServices()
    services.unexpected = True
    report, exc = start(services)
    _closed(report, exc, "RuntimeError")

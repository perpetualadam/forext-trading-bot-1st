"""Historical FILLED recovery repair. Real selection and startup, no database server."""

from __future__ import annotations

import atexit
import hashlib
import importlib.util
import json
import os
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
R11 = ROOT / "data" / "research" / "adaptive_ensemble" / "r11"
SYMBOL = "EUR_USD"

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PERSIST_EXEC_ORDERS"] = "0"
os.environ["LIVE_SAFETY_STATE_PATH"] = str(R11 / "synthetic_live_safety_state.json")

try:
    _probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
except RuntimeError as exc:
    if "NETWORK_BLOCKED" not in str(exc):
        raise
else:
    _probe.close()
    raise RuntimeError("R11_BLOCKED_TEST_ISOLATION")

from forex_bot.app import initialise_application, shutdown_application  # noqa: E402
from forex_bot import database as order_db  # noqa: E402
from forex_bot.database import (  # noqa: E402
    RECOVERY_FETCH_LIMIT,
    RECOVERY_SELECTION_SQL,
    RESERVATION_BLOCK_SQL,
    confirm_exposure_flat,
    exposure_entry_block_reason,
    exposure_marker_block_reason,
    fetch_exec_orders_open_for_recovery,
    order_status_proves_exposure_closed,
    reservation_status_block_reason,
    reset_order_intent_gate_for_tests,
    select_rows_for_recovery,
)
from forex_bot.live_safety import live_order_auth_state  # noqa: E402
from forex_bot.orders import (  # noqa: E402
    ingest_recovery_snapshot,
    load_open_orders_from_db_into_memory,
    orders_by_client_id,
    reset_orders_for_tests,
)
from forex_bot.positions import get_position, positions  # noqa: E402
from forex_bot.strategy_meta import strategies  # noqa: E402

_fake_spec = importlib.util.spec_from_file_location("r10_fakes", ROOT / "tests" / "r10_fakes.py")
assert _fake_spec is not None and _fake_spec.loader is not None
_fake_mod = importlib.util.module_from_spec(_fake_spec)
_fake_spec.loader.exec_module(_fake_mod)
OfflineServices = _fake_mod.OfflineServices

RESULTS: list[dict[str, object]] = []
PROTECTED = {
    "forex_bot/bot_loop.py": "6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796",
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


def _dump_results() -> None:
    R11.mkdir(parents=True, exist_ok=True)
    (R11 / "10_regression_test_results.json").write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")


atexit.register(_dump_results)


def setup_function() -> None:
    os.environ["PERSIST_EXEC_ORDERS"] = "0"
    os.environ["LIVE_SAFETY_STATE_PATH"] = str(R11 / "synthetic_live_safety_state.json")
    reset_order_intent_gate_for_tests()
    reset_orders_for_tests()
    positions.clear()
    order_db._pg_conn = None
    order_db._pg_cursor = None


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


def start(services):
    try:
        report = drive(initialise_application(services.ports()))
    except Exception as exc:
        return getattr(exc, "startup_report", None), exc
    return report, None


def record(test_id, function, source_function, expected, actual, status, fakes, evidence) -> None:
    RESULTS.append(
        {
            "test_id": test_id,
            "test_function": function,
            "source_function": source_function,
            "expected": expected,
            "actual": actual,
            "status": status,
            "fake_dependencies": fakes,
            "postgresql_sql_executed": False,
            "broker_contacted": False,
            "evidence": evidence,
        }
    )


def case(test_id, function, source_function, expected, fakes, evidence, body) -> None:
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
        record(test_id, function, source_function, expected, actual, status, fakes, evidence)


def _selected(status: str, **extra: object) -> bool:
    return any(item["status"] == status for item in select_rows_for_recovery([row(status, **extra)]))


class _Conn:
    closed = False


class _Cursor:
    def __init__(self, rows=None, fail: bool = False) -> None:
        self.rows = rows or []
        self.fail = fail
        self.sql = ""
        self.params = None

    def execute(self, sql, params=None) -> None:
        self.sql = sql
        self.params = params
        if self.fail:
            raise RuntimeError("query failed")

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return None


def _use_cursor(cursor: _Cursor):
    original = order_db.psycopg2.connect

    def blocked(*_args, **_kwargs):
        raise RuntimeError("psycopg2.connect called")

    order_db.psycopg2.connect = blocked
    order_db._pg_conn = _Conn()
    order_db._pg_cursor = cursor
    return original


def _restore_cursor(original) -> None:
    order_db.psycopg2.connect = original
    order_db._pg_conn = None
    order_db._pg_cursor = None


def test_i01_pending_selected() -> None:
    def body() -> str:
        assert _selected("PENDING")
        assert "PENDING" in RECOVERY_SELECTION_SQL
        return "selected"

    case("I01", "test_i01_pending_selected", "select_rows_for_recovery", "selected", "none", "Python predicate and SQL text; PostgreSQL not executed", body)


def test_i02_partial_selected() -> None:
    def body() -> str:
        assert _selected("PARTIAL")
        assert "PARTIAL" in RECOVERY_SELECTION_SQL
        return "selected"

    case("I02", "test_i02_partial_selected", "select_rows_for_recovery", "selected", "none", "Python predicate and SQL text", body)


def test_i03_unresolved_selected() -> None:
    def body() -> str:
        assert _selected("UNRESOLVED")
        assert "UNRESOLVED" in RECOVERY_SELECTION_SQL
        return "selected"

    case("I03", "test_i03_unresolved_selected", "select_rows_for_recovery", "selected", "none", "Python predicate and SQL text", body)


def test_i04_filled_unconfirmed_selected() -> None:
    def body() -> str:
        kept = select_rows_for_recovery([row("FILLED", metadata={"exposure_safety": "UNCONFIRMED"})])
        assert kept and "FILLED" in RECOVERY_SELECTION_SQL
        return "selected"

    case("I04", "test_i04_filled_unconfirmed_selected", "select_rows_for_recovery", "selected", "none", "UNCONFIRMED stays eligible", body)


def test_i05_historical_filled_missing_marker_selected() -> None:
    def body() -> str:
        payload = row("FILLED")
        del payload["metadata"]
        kept = select_rows_for_recovery([payload])
        assert len(kept) == 1
        assert "metadata" not in kept[0]
        return "selected"

    case("I05", "test_i05_historical_filled_missing_marker_selected", "select_rows_for_recovery", "selected", "none", "missing metadata is not flat", body)


def test_i06_null_metadata_selected() -> None:
    def body() -> str:
        kept = select_rows_for_recovery([row("FILLED", metadata=None)])
        assert len(kept) == 1
        assert exposure_marker_block_reason(kept[0]) == "exposure_unconfirmed"
        return "selected_not_flat"

    case("I06", "test_i06_null_metadata_selected", "exposure_marker_block_reason", "selected", "none", "NULL metadata stays uncertain", body)


def test_i07_empty_metadata_selected() -> None:
    def body() -> str:
        kept = select_rows_for_recovery([row("FILLED", metadata={})])
        assert len(kept) == 1
        assert exposure_marker_block_reason(kept[0]) == "exposure_unconfirmed"
        return "selected_not_flat"

    case("I07", "test_i07_empty_metadata_selected", "exposure_marker_block_reason", "selected", "none", "empty object is not flat", body)


def test_i08_malformed_metadata_fails_closed() -> None:
    def body() -> str:
        kept = select_rows_for_recovery([row("FILLED", metadata="legacy-text")])
        assert len(kept) == 1
        with pytest.raises(order_db.OrderRecoveryUnreadable):
            ingest_recovery_snapshot(kept, True)
        assert order_db._process_fail_closed is True
        return "malformed_fail_closed"

    case("I08", "test_i08_malformed_metadata_fails_closed", "ingest_recovery_snapshot", "fail closed", "none", "malformed metadata is not dropped or treated as flat", body)


def test_i09_unknown_marker_fails_closed() -> None:
    def body() -> str:
        kept = select_rows_for_recovery([row("FILLED", metadata={"exposure_safety": "GUESS"})])
        with pytest.raises(order_db.OrderRecoveryUnreadable):
            ingest_recovery_snapshot(kept, True)
        return "unknown_marker_fail_closed"

    case("I09", "test_i09_unknown_marker_fails_closed", "ingest_recovery_snapshot", "fail closed", "none", "unknown marker is selected and then rejected", body)


def test_i10_confirmed_flat_does_not_override_unresolved() -> None:
    def body() -> str:
        rows = [
            row("FILLED", "flat", metadata={"exposure_safety": "CONFIRMED_FLAT"}),
            row("UNRESOLVED", "amb"),
        ]
        kept = select_rows_for_recovery(rows)
        assert [item["client_order_id"] for item in kept] == ["amb"]
        ingest_recovery_snapshot(kept, True)
        assert confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False
        assert exposure_entry_block_reason(SYMBOL) == "unresolved_intent"
        return "unresolved_kept"

    case("I10", "test_i10_confirmed_flat_does_not_override_unresolved", "select_rows_for_recovery", "unresolved remains", "none", "flat token is not broker evidence and does not hide UNRESOLVED", body)


def test_i11_sql_parameters_inspected() -> None:
    def body() -> str:
        cursor = _Cursor(rows=[])
        original = _use_cursor(cursor)
        try:
            fetch_exec_orders_open_for_recovery()
        finally:
            _restore_cursor(original)
        assert cursor.params is None
        assert "%s" not in cursor.sql
        assert "PENDING" in cursor.sql and "PARTIAL" in cursor.sql and "UNRESOLVED" in cursor.sql
        assert "status = 'FILLED'" in cursor.sql
        assert "CONFIRMED_FLAT" in cursor.sql
        return "static_sql"

    case("I11", "test_i11_sql_parameters_inspected", "fetch_exec_orders_open_for_recovery", "no user parameters", "fake cursor", "captured SQL text only; PostgreSQL did not execute it", body)


def test_i12_query_exception_fails_closed() -> None:
    def body() -> str:
        cursor = _Cursor(fail=True)
        original = _use_cursor(cursor)
        try:
            with pytest.raises(order_db.OrderRecoveryUnreadable):
                fetch_exec_orders_open_for_recovery()
            assert load_open_orders_from_db_into_memory() == 0
        finally:
            _restore_cursor(original)
        assert order_db._process_fail_closed is True
        return "fail_closed"

    case("I12", "test_i12_query_exception_fails_closed", "load_open_orders_from_db_into_memory", "fail closed", "fake cursor", "exception path; no PostgreSQL connection", body)


def test_i13_no_schema_migration() -> None:
    def body() -> str:
        assert "ALTER " not in RECOVERY_SELECTION_SQL
        assert "CREATE " not in RECOVERY_SELECTION_SQL
        for relative, expected in PROTECTED.items():
            digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            assert digest == expected, relative
        return "no_migration"

    case("I13", "test_i13_no_schema_migration", "RECOVERY_SELECTION_SQL", "schema unchanged", "none", "selection text has no DDL; protected files match", body)


def test_i14_postgresql_not_contacted() -> None:
    def body() -> str:
        assert order_db._pg_conn is None
        return "no_connection"

    case("I14", "test_i14_postgresql_not_contacted", "none", "no connection", "none", "shared connection remains unset", body)


def test_i15_legacy_filled_ingested() -> None:
    def body() -> str:
        payload = row("FILLED", "legacy")
        del payload["metadata"]
        count = ingest_recovery_snapshot(select_rows_for_recovery([payload]), True)
        assert count == 1
        assert orders_by_client_id["legacy"].status.value == "FILLED"
        return "ingested"

    case("I15", "test_i15_legacy_filled_ingested", "ingest_recovery_snapshot", "ingested", "none", "legacy row is retained", body)


def test_i16_legacy_filled_blocks_entry() -> None:
    def body() -> str:
        ingest_recovery_snapshot(select_rows_for_recovery([row("FILLED", "legacy")]), True)
        assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"
        assert order_status_proves_exposure_closed("FILLED") is False
        assert get_position(SYMBOL) is None
        return "exposure_unconfirmed"

    case("I16", "test_i16_legacy_filled_blocks_entry", "exposure_entry_block_reason", "blocked", "none", "missing position is not flat", body)


def test_i17_multiple_filled_rows_preserve_uncertainty() -> None:
    def body() -> str:
        rows = [row("FILLED", "a"), row("FILLED", "b", side="SELL")]
        ingest_recovery_snapshot(select_rows_for_recovery(rows), True)
        assert set(orders_by_client_id) == {"a", "b"}
        assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"
        return "both_retained"

    case("I17", "test_i17_multiple_filled_rows_preserve_uncertainty", "ingest_recovery_snapshot", "both retained", "none", "order book keeps both rows", body)


def test_i18_filled_plus_pending_blocks() -> None:
    def body() -> str:
        rows = [row("FILLED", "fill"), row("PENDING", "pend")]
        ingest_recovery_snapshot(select_rows_for_recovery(rows), True)
        assert exposure_entry_block_reason(SYMBOL) is not None
        return exposure_entry_block_reason(SYMBOL) or ""

    case("I18", "test_i18_filled_plus_pending_blocks", "exposure_entry_block_reason", "blocked", "none", "both rows selected", body)


def test_i19_filled_plus_unresolved_blocks() -> None:
    def body() -> str:
        rows = [row("FILLED", "fill"), row("UNRESOLVED", "amb")]
        ingest_recovery_snapshot(select_rows_for_recovery(rows), True)
        assert confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False
        assert exposure_entry_block_reason(SYMBOL) is not None
        return "blocked"

    case("I19", "test_i19_filled_plus_unresolved_blocks", "confirm_exposure_flat", "blocked", "none", "flat token cannot clear the unresolved order", body)


def test_i20_corrupt_row_fails_closed() -> None:
    def body() -> str:
        with pytest.raises(order_db.OrderRecoveryUnreadable):
            select_rows_for_recovery([row("NOT_A_STATUS")])
        assert order_db._process_fail_closed is True
        return "fail_closed"

    case("I20", "test_i20_corrupt_row_fails_closed", "select_rows_for_recovery", "fail closed", "none", "unknown status is not dropped", body)


def test_i21_missing_symbol_fails_closed() -> None:
    def body() -> str:
        with pytest.raises(order_db.OrderRecoveryUnreadable):
            ingest_recovery_snapshot(select_rows_for_recovery([{"status": "PENDING", "client_order_id": "x"}]), True)
        return "fail_closed"

    case("I21", "test_i21_missing_symbol_fails_closed", "ingest_recovery_snapshot", "fail closed", "none", "selected row still requires a symbol", body)


def test_i22_missing_client_id_fails_closed() -> None:
    def body() -> str:
        with pytest.raises(order_db.OrderRecoveryUnreadable):
            ingest_recovery_snapshot(select_rows_for_recovery([row("PENDING", "")]), True)
        return "fail_closed"

    case("I22", "test_i22_missing_client_id_fails_closed", "ingest_recovery_snapshot", "fail closed", "none", "empty client id is rejected", body)


def test_i23_duplicate_recovery_idempotent() -> None:
    def body() -> str:
        rows = [row("FILLED", "same"), row("FILLED", "same")]
        ingest_recovery_snapshot(select_rows_for_recovery(rows), True)
        ingest_recovery_snapshot(select_rows_for_recovery(rows), True)
        assert len(orders_by_client_id) == 1
        return "one_order"

    case("I23", "test_i23_duplicate_recovery_idempotent", "ingest_recovery_snapshot", "one order", "none", "identical client id is not duplicated", body)


def test_i24_conflicting_rows_fail_closed() -> None:
    def body() -> str:
        rows = [row("FILLED", "same", symbol=SYMBOL), row("PENDING", "same", symbol="GBP_USD")]
        with pytest.raises(order_db.OrderRecoveryUnreadable):
            ingest_recovery_snapshot(select_rows_for_recovery(rows), True)
        assert order_db._process_fail_closed is True
        return "conflict_fail_closed"

    case("I24", "test_i24_conflicting_rows_fail_closed", "ingest_recovery_snapshot", "fail closed", "none", "same client id with a different identity is not overwritten", body)


def test_i25_empty_success_differs_from_failed_read() -> None:
    def body() -> str:
        assert select_rows_for_recovery([]) == []
        assert order_db._process_fail_closed is False
        cursor = _Cursor(rows=[])
        original = _use_cursor(cursor)
        try:
            assert fetch_exec_orders_open_for_recovery() == []
            assert load_open_orders_from_db_into_memory() == 0
            assert order_db._process_fail_closed is False
        finally:
            _restore_cursor(original)
        return "empty_not_failure"

    case("I25", "test_i25_empty_success_differs_from_failed_read", "fetch_exec_orders_open_for_recovery", "empty is not a failure", "fake cursor", "empty cursor result does not fail-close; a raised query does", body)


def test_i26_real_offline_initialization_executes() -> None:
    def body() -> str:
        report, exc = start(OfflineServices())
        assert exc is None and report.offline_ready is True and report.trading_ready is False
        assert report.phases[-1] == "offline_initialization_ready"
        return "offline_initialization_ready"

    case("I26", "test_i26_real_offline_initialization_executes", "initialise_application", "offline ready", "full fake bundle", "real startup seam", body)


def test_i27_fake_recovery_includes_historical_filled() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("FILLED", "legacy"), row("CANCELLED", "done")]
        report, exc = start(services)
        assert exc is None and report.offline_ready is True
        assert "legacy" in orders_by_client_id
        assert "done" not in orders_by_client_id
        return "legacy_kept"

    case("I27", "test_i27_fake_recovery_includes_historical_filled", "initialise_application", "legacy row kept", "fake recovery rows", "startup called select_rows_for_recovery before ingest", body)


def test_i28_startup_preserves_historical_exposure_hold() -> None:
    def body() -> str:
        services = OfflineServices()
        legacy = row("FILLED", "legacy")
        del legacy["metadata"]
        services.rows = [legacy]
        report, exc = start(services)
        assert exc is None
        assert report.exposure[SYMBOL] == "exposure_unconfirmed"
        assert get_position(SYMBOL) is None
        return "exposure_unconfirmed"

    case("I28", "test_i28_startup_preserves_historical_exposure_hold", "initialise_application", "hold", "historical FILLED row", "startup does not treat the missing marker as flat", body)


def test_i29_corrupt_recovery_fails_closed() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("NOT_A_STATUS")]
        report, exc = start(services)
        assert exc is not None and report.offline_ready is False and report.trading_ready is False
        return report.error

    case("I29", "test_i29_corrupt_recovery_fails_closed", "initialise_application", "fail closed", "corrupt row", "ready phase absent", body)


def test_i30_failed_recovery_fails_closed() -> None:
    def body() -> str:
        services = OfflineServices()
        services.use_provider = True
        services.fail = "recovery"
        report, exc = start(services)
        assert report.offline_ready is False and report.trading_ready is False
        assert "persistence" in services.closed
        return report.error

    case("I30", "test_i30_failed_recovery_fails_closed", "initialise_application", "fail closed", "recovery provider", "partial startup closes persistence", body)


def test_i31_reconciliation_unavailable_preserves_uncertainty() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("FILLED", "legacy")]
        services.reconciliation_unavailable = True
        report, exc = start(services)
        assert exc is None and report.offline_ready is True
        assert report.reconciliation == "ReconciliationUnavailable"
        assert report.exposure[SYMBOL] == "exposure_unconfirmed"
        assert report.trading_ready is False
        return "hold_kept"

    case("I31", "test_i31_reconciliation_unavailable_preserves_uncertainty", "initialise_application", "hold kept", "fake market data", "unavailable reconciliation does not clear exposure", body)


def test_i32_multiple_filled_rows_startup() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("FILLED", "a"), row("FILLED", "b")]
        report, exc = start(services)
        assert exc is None
        assert set(orders_by_client_id) == {"a", "b"}
        assert report.exposure[SYMBOL] == "exposure_unconfirmed"
        return "both_held"

    case("I32", "test_i32_multiple_filled_rows_startup", "initialise_application", "both held", "two FILLED rows", "neither row is discarded", body)


def test_i33_unresolved_order_remains_blocked() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("FILLED", "fill", metadata={"exposure_safety": "CONFIRMED_FLAT"}), row("UNRESOLVED", "amb")]
        report, exc = start(services)
        assert exc is None
        assert "fill" not in orders_by_client_id
        assert "amb" in orders_by_client_id
        assert confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False
        assert report.trading_ready is False
        return "unresolved_blocked"

    case("I33", "test_i33_unresolved_order_remains_blocked", "initialise_application", "blocked", "flat token plus UNRESOLVED", "internal flat token does not clear the unresolved order", body)


def test_i34_offline_ready_is_not_trading_ready() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("FILLED", "legacy")]
        report, exc = start(services)
        assert report.offline_ready is True and report.trading_ready is False
        assert "running" not in report.phases
        return "offline_only"

    case("I34", "test_i34_offline_ready_is_not_trading_ready", "initialise_application", "not trading ready", "historical FILLED", "ready means offline initialization only", body)


def test_i35_live_permission_remains_blocked() -> None:
    def body() -> str:
        report, exc = start(OfflineServices())
        assert exc is None
        assert live_order_auth_state() == "BLOCKED"
        assert all(item.active is False for item in strategies.values())
        return "BLOCKED"

    case("I35", "test_i35_live_permission_remains_blocked", "initialise_fail_closed", "BLOCKED", "verify_safety", "strategies stay inactive", body)


def test_i36_no_run_bot_scheduling() -> None:
    def body() -> str:
        services = OfflineServices()
        report, exc = start(services)
        assert report.trading_loop_started is False
        assert services.schedule_status == "recorded_not_started"
        assert "forex_bot.bot_loop" not in sys.modules
        return "not_scheduled"

    case("I36", "test_i36_no_run_bot_scheduling", "initialise_application", "not scheduled", "fake scheduler", "run_bot was not imported", body)


def test_i37_no_broker_request() -> None:
    def body() -> str:
        services = OfflineServices()
        start(services)
        assert services.rejected == []
        with pytest.raises(RuntimeError):
            services.submit_order()
        return "no_submit_during_startup"

    case("I37", "test_i37_no_broker_request", "initialise_application", "no submit", "fake broker", "startup recorded no order submission", body)


def test_i38_no_postgresql_connection() -> None:
    def body() -> str:
        start(OfflineServices())
        assert order_db._pg_conn is None
        return "no_connection"

    case("I38", "test_i38_no_postgresql_connection", "initialise_application", "no connection", "fake persistence", "startup did not open PostgreSQL", body)


def test_i39_no_network() -> None:
    def body() -> str:
        with pytest.raises(RuntimeError, match="NETWORK_BLOCKED"):
            socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with pytest.raises(RuntimeError, match="DNS_BLOCKED"):
            socket.getaddrinfo("example.invalid", 80)
        return "blocked"

    case("I39", "test_i39_no_network", "none", "blocked", "socket barrier", "AF_INET and DNS raise", body)


def test_i40_clean_shutdown() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("FILLED", "legacy")]
        report, exc = start(services)
        shutdown_application(services.ports(), report)
        assert services.open == []
        assert report.trading_ready is False
        assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"
        return "closed_hold_remains"

    case("I40", "test_i40_clean_shutdown", "shutdown_application", "closed", "full fake bundle", "shutdown does not release the exposure hold", body)


def test_i41_pending_reservation() -> None:
    def body() -> str:
        from forex_bot.orders import try_begin_order_submission

        services = OfflineServices()
        services.rows = [row("PENDING", "held")]
        start(services)
        assert reservation_status_block_reason("PENDING") == "active_reservation"
        assert try_begin_order_submission(client_order_id="new", symbol=SYMBOL, direction="BUY", units=1) is False
        return "blocked"

    case("I41", "test_i41_pending_reservation", "try_begin_order_submission", "blocked", "PENDING row", "R.8 pending hold", body)


def test_i42_partial_reservation() -> None:
    def body() -> str:
        from forex_bot.orders import try_begin_order_submission

        services = OfflineServices()
        services.rows = [row("PARTIAL", "part")]
        start(services)
        assert try_begin_order_submission(client_order_id="new", symbol=SYMBOL, direction="BUY", units=1) is False
        return "blocked"

    case("I42", "test_i42_partial_reservation", "try_begin_order_submission", "blocked", "PARTIAL row", "R.8 partial hold", body)


def test_i43_unresolved_reservation() -> None:
    def body() -> str:
        from forex_bot.orders import try_begin_order_submission

        services = OfflineServices()
        services.rows = [row("UNRESOLVED", "amb")]
        start(services)
        assert try_begin_order_submission(client_order_id="new", symbol=SYMBOL, direction="BUY", units=1) is False
        return "blocked"

    case("I43", "test_i43_unresolved_reservation", "try_begin_order_submission", "blocked", "UNRESOLVED row", "R.8 unresolved hold", body)


def test_i44_filled_exposure_hold() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("FILLED", "fill", metadata={"exposure_safety": "UNCONFIRMED"})]
        start(services)
        assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"
        return "exposure_unconfirmed"

    case("I44", "test_i44_filled_exposure_hold", "exposure_entry_block_reason", "hold", "UNCONFIRMED row", "R.9 fill hold", body)


def test_i45_missing_position_hold() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("FILLED", "legacy")]
        start(services)
        assert get_position(SYMBOL) is None
        assert exposure_entry_block_reason(SYMBOL) == "exposure_unconfirmed"
        return "hold_without_position"

    case("I45", "test_i45_missing_position_hold", "exposure_entry_block_reason", "hold", "legacy FILLED", "R.9 missing position", body)


def test_i46_flat_token_restriction() -> None:
    def body() -> str:
        services = OfflineServices()
        services.rows = [row("UNRESOLVED", "amb")]
        start(services)
        assert confirm_exposure_flat(SYMBOL, evidence="CONFIRMED_FLAT") is False
        return "refused"

    case("I46", "test_i46_flat_token_restriction", "confirm_exposure_flat", "refused", "UNRESOLVED row", "R.9 flat token restriction", body)


def test_i47_invalid_direction_block() -> None:
    def body() -> str:
        from forex_bot.bot_loop import direction_action_gate

        called: list[str] = []
        assert direction_action_gate("HOLD", called.append, called.append, called.append) is None
        assert called == []
        return "blocked"

    case("I47", "test_i47_invalid_direction_block", "direction_action_gate", "blocked", "none", "sender was not called", body)


def test_i48_inactive_strategy_block() -> None:
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
        return reason

    case("I48", "test_i48_inactive_strategy_block", "strategy_entry_block_reason", "STRATEGY_INACTIVE", "none", "inactive strategy stops before sizing", body)


def test_i49_live_authorisation_block() -> None:
    def body() -> str:
        from forex_bot.bot_loop import strategy_entry_block_reason

        start(OfflineServices())
        reason = strategy_entry_block_reason(
            "sma_cross",
            active=True,
            authorised_for_live=False,
            safety_initialised=True,
            known_strategy=True,
        )
        assert reason == "STRATEGY_NOT_AUTHORISED"
        assert live_order_auth_state() == "BLOCKED"
        return reason

    case("I49", "test_i49_live_authorisation_block", "strategy_entry_block_reason", "STRATEGY_NOT_AUTHORISED", "verify_safety", "live orders stay blocked", body)


def test_i50_no_duplicate_dispatch() -> None:
    def body() -> str:
        from forex_bot.orders import try_begin_order_submission

        services = OfflineServices()
        services.rows = [row("FILLED", "legacy")]
        start(services)
        assert try_begin_order_submission(client_order_id="new", symbol=SYMBOL, direction="BUY", units=1) is False
        assert services.rejected == []
        assert "FILLED" in RESERVATION_BLOCK_SQL
        return "no_dispatch"

    case("I50", "test_i50_no_duplicate_dispatch", "try_begin_order_submission", "no dispatch", "legacy FILLED", "reservation SQL also treats unmarked FILLED as blocking; SQL was not executed", body)


def test_i51_postgresql_sql_not_evaluated() -> None:
    record("I51", "test_i51_postgresql_sql_not_evaluated", "none", "NOT_EVALUATED", "NOT_EVALUATED", "NOT_EVALUATED", "none", "PostgreSQL did not execute the SQL")
    pytest.skip("NOT_EVALUATED")


def test_i52_postgresql_recovery_not_evaluated() -> None:
    record("I52", "test_i52_postgresql_recovery_not_evaluated", "none", "NOT_EVALUATED", "NOT_EVALUATED", "NOT_EVALUATED", "none", "no database recovery")
    pytest.skip("NOT_EVALUATED")


def test_i53_broker_reconciliation_not_evaluated() -> None:
    record("I53", "test_i53_broker_reconciliation_not_evaluated", "none", "NOT_EVALUATED", "NOT_EVALUATED", "NOT_EVALUATED", "none", "no broker reconciliation")
    pytest.skip("NOT_EVALUATED")


def test_i54_production_launcher_not_evaluated() -> None:
    record("I54", "test_i54_production_launcher_not_evaluated", "lifespan", "NOT_EVALUATED", "NOT_EVALUATED", "NOT_EVALUATED", "none", "production lifespan was not entered")
    pytest.skip("NOT_EVALUATED")


def test_i55_durable_position_recovery_not_evaluated() -> None:
    record("I55", "test_i55_durable_position_recovery_not_evaluated", "none", "NOT_EVALUATED", "NOT_EVALUATED", "NOT_EVALUATED", "none", "no position table and no migration")
    pytest.skip("NOT_EVALUATED")


def test_truncation_fails_closed() -> None:
    cursor = _Cursor(rows=[(None,)] * (RECOVERY_FETCH_LIMIT + 1))
    original = _use_cursor(cursor)
    try:
        with pytest.raises(order_db.OrderRecoveryUnreadable, match="truncated"):
            fetch_exec_orders_open_for_recovery()
    finally:
        _restore_cursor(original)

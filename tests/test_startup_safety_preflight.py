"""Startup preflight tests. Reads app.py as text. Does not import it."""

from __future__ import annotations

import ast
import json
import socket
import sys
from pathlib import Path

import pytest

from forex_bot.live_safety import (
    AUTH_ALLOWED,
    AUTH_BLOCKED,
    REASON_CORRUPT,
    REASON_DEFAULT_DENY,
    REASON_FUTURE_SCHEMA,
    REASON_UNREADABLE,
    SafetyStateProtected,
    _blank_document,
    initialise_fail_closed,
    live_order_auth_reason,
    live_order_auth_state,
    live_safety_initialised,
    operator_set_strategy_active,
    persist_evolve_disable,
    state_path,
)
from forex_bot.strategy_meta import (
    SCALP_STRATEGY_KEYS,
    SWING_STRATEGY_KEYS,
    Strategy,
    strategies,
)

STRATEGY_NAMES = tuple(dict.fromkeys((*SCALP_STRATEGY_KEYS, *SWING_STRATEGY_KEYS)))
_APP_PATH = Path("forex_bot/app.py")


def _path() -> Path:
    path = state_path()
    text = str(path)
    assert "data\\ops" not in text
    assert "data/ops" not in text.replace("\\", "/")
    assert "v2_shadow" not in text
    return path


def _write(payload: bytes) -> Path:
    path = _path()
    path.write_bytes(payload)
    return path


def _compatible() -> bool:
    """Predicate used by lifespan. This does not call lifespan."""
    initialise_fail_closed()
    return live_safety_initialised()


def _inactive() -> None:
    assert live_order_auth_state() == AUTH_BLOCKED
    for name in STRATEGY_NAMES:
        assert strategies[name].active is False


def _lifespan_source() -> str:
    source = _APP_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "lifespan":
            segment = ast.get_source_segment(source, node)
            assert segment is not None
            return segment
    raise AssertionError("lifespan not found")


def _abort_before(fragment: str) -> None:
    source = _lifespan_source()
    abort = source.index("raise StartupSafetyAbort")
    assert abort < source.index(fragment)


def test_t01_valid_blocked_state_is_startup_compatible() -> None:
    document = _blank_document(reason="operator_preflight_blocked")
    _write(json.dumps(document).encode("utf-8"))
    assert _compatible() is True


def test_t02_blocked_remains_blocked_after_preflight() -> None:
    document = _blank_document(reason="operator_preflight_blocked")
    _write(json.dumps(document).encode("utf-8"))
    assert _compatible() is True
    assert live_order_auth_state() == AUTH_BLOCKED


def test_t03_valid_state_does_not_grant_authorisation() -> None:
    document = _blank_document(reason="previous_process")
    document["live_order_authorisation"]["state"] = AUTH_ALLOWED
    _write(json.dumps(document).encode("utf-8"))
    assert _compatible() is True
    assert live_order_auth_state() == AUTH_BLOCKED


def test_t04_missing_file_follows_established_creation() -> None:
    path = _path()
    assert not path.exists()
    assert _compatible() is True
    assert path.is_file()


def test_t05_missing_file_is_blocked() -> None:
    assert not _path().exists()
    assert _compatible() is True
    assert live_order_auth_state() == AUTH_BLOCKED
    loaded = json.loads(_path().read_text(encoding="utf-8"))
    assert loaded["live_order_authorisation"]["state"] == AUTH_BLOCKED


def test_t06_missing_file_leaves_strategies_inactive() -> None:
    assert not _path().exists()
    assert _compatible() is True
    _inactive()


def test_t07_corrupt_json_is_not_startup_compatible() -> None:
    _write(b"{not-json")
    assert _compatible() is False
    assert live_order_auth_reason() == REASON_CORRUPT


def test_t08_corrupt_json_bytes_remain() -> None:
    original = b"{not-json"
    path = _write(original)
    assert _compatible() is False
    assert path.read_bytes() == original


def test_t09_future_schema_is_not_startup_compatible() -> None:
    _write(b'{"schema_version": 2}\n')
    assert _compatible() is False
    assert live_order_auth_reason() == REASON_FUTURE_SCHEMA


def test_t10_future_schema_bytes_remain() -> None:
    original = b'{"schema_version": 2}\n'
    path = _write(original)
    assert _compatible() is False
    assert path.read_bytes() == original


def test_t11_invalid_document_is_not_startup_compatible() -> None:
    document = _blank_document(reason="operator_preflight_blocked")
    document["strategies"]["scalp"]["active"] = "false"
    _write(json.dumps(document).encode("utf-8"))
    assert _compatible() is False


def test_t12_invalid_document_bytes_remain() -> None:
    document = _blank_document(reason="operator_preflight_blocked")
    document["strategies"]["scalp"]["active"] = "false"
    original = json.dumps(document).encode("utf-8")
    path = _write(original)
    assert _compatible() is False
    assert path.read_bytes() == original


def test_t13_unreadable_file_is_not_startup_compatible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = b'{"schema_version": 1}\n'
    path = _write(original)

    def denied(_path: Path) -> str:
        raise OSError("synthetic unreadable")

    monkeypatch.setattr("forex_bot.live_safety._read_text", denied)
    assert _compatible() is False
    assert live_order_auth_reason() == REASON_UNREADABLE
    assert path.read_bytes() == original


def test_t14_permission_error_is_not_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = b'{"schema_version": 3}\n'
    path = _write(original)

    def denied(_path: Path) -> str:
        raise PermissionError("synthetic denial")

    monkeypatch.setattr("forex_bot.live_safety._read_text", denied)
    assert _compatible() is False
    assert live_order_auth_reason() == REASON_UNREADABLE
    assert live_order_auth_reason() != REASON_DEFAULT_DENY
    assert path.read_bytes() == original
    assert path.exists()


def test_t15_unclassified_failure_is_not_startup_compatible() -> None:
    _write(b"[]")
    assert _compatible() is False
    source = _lifespan_source()
    abort = source.index("raise StartupSafetyAbort")
    assert source.index("if not live_safety_initialised()") < abort
    assert "except StartupSafetyAbort" not in source


def test_t16_abort_is_before_database_initialization() -> None:
    _write(b"{not-json")
    assert _compatible() is False
    _abort_before("get_connection()")


def test_t17_abort_is_before_broker_initialization() -> None:
    _write(b"{not-json")
    assert _compatible() is False
    _abort_before("build_api()")


def test_t18_abort_is_before_broker_account_request() -> None:
    _write(b"{not-json")
    assert _compatible() is False
    _abort_before("fetch_account_summary")


def test_t19_abort_is_before_reconciliation() -> None:
    _write(b"{not-json")
    assert _compatible() is False
    _abort_before("run_reconciliation_once")


def test_t20_abort_is_before_scheduler_tasks() -> None:
    _write(b"{not-json")
    assert _compatible() is False
    _abort_before("create_task(reconciliation_loop())")


def test_t21_abort_is_before_trading_loop() -> None:
    _write(b"{not-json")
    assert _compatible() is False
    _abort_before("create_task(run_bot())")


def test_t22_abort_is_before_other_background_tasks() -> None:
    _write(b"{not-json")
    assert _compatible() is False
    _abort_before("create_task(health_snapshot_loop())")
    _abort_before("create_task(telegram_inbound_loop())")
    _abort_before("start_telegram_control()")


def test_t23_startup_failure_reason_is_observable() -> None:
    _write(b'{"schema_version": 8}\n')
    assert _compatible() is False
    reason = live_order_auth_reason()
    assert reason == REASON_FUTURE_SCHEMA
    source = _lifespan_source()
    assert "reason=%s" in source
    assert "reason={reason}" in source


def test_t24_failure_text_has_no_credential_fields() -> None:
    source = _lifespan_source()
    lowered = source.lower()
    assert "oanda_access_token" not in lowered
    assert "postgres_pass" not in lowered
    assert "api_key" not in lowered
    _write(b"{not-json")
    assert _compatible() is False
    assert "token" not in live_order_auth_reason().lower()


def test_t25_failure_does_not_expose_document_contents() -> None:
    original = b'{"schema_version": 2, "secret_marker": "synthetic-marker"}\n'
    _write(original)
    assert _compatible() is False
    reason = live_order_auth_reason()
    assert "synthetic-marker" not in reason
    assert "secret_marker" not in reason
    assert "{" not in reason


def test_t26_abort_cannot_grant_allowed() -> None:
    payload = (
        b'{"schema_version": 2, "live_order_authorisation": {"state": "ALLOWED"}}\n'
    )
    _write(payload)
    assert _compatible() is False
    assert live_order_auth_state() == AUTH_BLOCKED


def test_t27_abort_does_not_activate_strategies() -> None:
    _write(b"{not-json")
    assert _compatible() is False
    _inactive()


def test_t28_valid_blocked_keeps_downstream_startup_in_source() -> None:
    document = _blank_document(reason="operator_preflight_blocked")
    _write(json.dumps(document).encode("utf-8"))
    assert _compatible() is True
    source = _lifespan_source()
    assert "get_connection()" in source
    assert "build_api()" in source
    assert "create_task(run_bot())" in source


def test_t29_successful_preflight_keeps_existing_order() -> None:
    source = _lifespan_source()
    order = [
        "initialise_fail_closed()",
        "if not live_safety_initialised()",
        "raise StartupSafetyAbort",
        'set_lifespan_phase("starting")',
        "get_connection()",
        "load_open_orders_from_db_into_memory()",
        "load_reconcile_state_from_db()",
        "build_api()",
        "await asyncio.to_thread(fetch_account_summary)",
        "await asyncio.to_thread(run_reconciliation_once)",
        "create_task(reconciliation_loop())",
        "create_task(run_bot())",
        "start_telegram_control()",
    ]
    positions = [source.index(item) for item in order]
    assert positions == sorted(positions)


def test_t30_unknown_fields_still_survive() -> None:
    document = _blank_document(reason="operator_preflight_blocked")
    document["future_metadata"] = {"preserve": True}
    document["strategies"]["trend"]["future_policy"] = {"mode": "synthetic"}
    _write(json.dumps(document).encode("utf-8"))
    assert _compatible() is True
    loaded = json.loads(_path().read_text(encoding="utf-8"))
    assert loaded["future_metadata"] == {"preserve": True}
    row = loaded["strategies"]["trend"]["future_policy"]
    assert row == {"mode": "synthetic"}


def test_t31_future_schema_protection_still_holds() -> None:
    original = b'{"schema_version": 6}\n'
    path = _write(original)
    assert _compatible() is False
    assert path.read_bytes() == original


def test_t32_corrupt_preservation_still_holds() -> None:
    original = b'{"schema_version": '
    path = _write(original)
    assert _compatible() is False
    assert path.read_bytes() == original


def test_t33_replace_failure_preserves_original(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _blank_document(reason="operator_preflight_blocked")
    path = _write(json.dumps(document).encode("utf-8"))
    original = path.read_bytes()

    def denied(_src: Path, _dst: Path) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr("forex_bot.live_safety.os.replace", denied)
    assert _compatible() is False
    assert path.read_bytes() == original


def test_t34_construction_remains_inactive() -> None:
    assert Strategy("scalp").active is False


def test_t35_invalid_assignment_does_not_activate() -> None:
    strategy = Strategy("trend")
    strategy.active = "false"
    strategy.active = 1
    assert strategy.active is False


def test_t36_all_six_fresh_strategies_are_inactive() -> None:
    assert set(STRATEGY_NAMES) == {
        "scalp",
        "trend",
        "mean_reversion",
        "swing_trend",
        "swing_mean_reversion",
        "swing_breakout",
    }
    assert all(Strategy(name).active is False for name in STRATEGY_NAMES)


def test_t37_operator_activation_still_requires_confirmation() -> None:
    assert _compatible() is True
    with pytest.raises(PermissionError):
        operator_set_strategy_active(
            name="scalp",
            active=True,
            reason="unconfirmed",
            operator_confirmed=False,
        )
    assert strategies["scalp"].active is False
    operator_set_strategy_active(
        name="scalp",
        active=True,
        reason="synthetic_operator",
        operator_confirmed=True,
    )
    assert strategies["scalp"].active is True
    operator_set_strategy_active(
        name="scalp",
        active=False,
        reason="synthetic_clear",
        operator_confirmed=True,
    )
    assert strategies["scalp"].active is False
    assert live_order_auth_state() == AUTH_BLOCKED


def test_t38_no_network_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def rejected(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network socket")

    monkeypatch.setattr(socket, "socket", rejected)
    document = _blank_document(reason="operator_preflight_blocked")
    _write(json.dumps(document).encode("utf-8"))
    assert _compatible() is True


def test_t39_no_database_module_loaded() -> None:
    assert "forex_bot.database" not in sys.modules
    assert "psycopg2" not in sys.modules


def test_t40_safety_path_is_not_operational_state() -> None:
    text = str(_path())
    assert "data\\ops" not in text
    assert "data/ops" not in text.replace("\\", "/")


def test_t41_safety_path_is_not_shadow_state() -> None:
    assert "v2_shadow" not in str(_path())


def test_t42_application_module_is_not_imported() -> None:
    assert "forex_bot.app" not in sys.modules
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module != "forex_bot.app"
        if isinstance(node, ast.Import):
            assert all(alias.name != "forex_bot.app" for alias in node.names)


def test_t43_scheduler_module_is_not_imported() -> None:
    assert "forex_bot.bot_loop" not in sys.modules
    _abort_before("create_task(run_bot())")


def test_t44_trading_loop_is_not_called() -> None:
    assert "forex_bot.bot_loop" not in sys.modules
    source = _lifespan_source()
    assert source.index("raise StartupSafetyAbort") < source.index("run_bot()")


def test_t45_order_router_module_is_not_loaded() -> None:
    assert "forex_bot.oanda_exec" not in sys.modules
    assert "forex_bot.oanda_client" not in sys.modules


def test_t46_account_summary_handler_remains_after_guard() -> None:
    source = _lifespan_source()
    abort = source.index("raise StartupSafetyAbort")
    handler = source.index('logger.warning("startup AccountSummary: %s", exc)')
    assert abort < handler
    assert "except Exception as exc:" in source


def test_t47_protected_preflight_does_not_retry_a_write() -> None:
    original = b'{"schema_version": 7}\n'
    path = _write(original)
    assert _compatible() is False
    assert _compatible() is False
    assert path.read_bytes() == original
    source = _lifespan_source()
    start = source.index("if not live_safety_initialised()")
    stop = source.index("raise StartupSafetyAbort")
    guard = source[start:stop]
    assert "for " not in guard
    assert "while " not in guard


def test_t48_repeated_protected_reads_keep_bytes() -> None:
    original = b'{"schema_version": 11, "keep": 1}\n'
    path = _write(original)
    for _ in range(3):
        assert _compatible() is False
    assert path.read_bytes() == original


def test_t49_protected_exception_does_not_continue() -> None:
    original = b'{"schema_version": 12}\n'
    path = _write(original)
    assert _compatible() is False
    downstream: list[str] = []

    def synthetic_startup() -> None:
        initialise_fail_closed()
        if not live_safety_initialised():
            return
        downstream.append("database")

    synthetic_startup()
    assert downstream == []
    with pytest.raises(SafetyStateProtected):
        persist_evolve_disable("scalp", sample_count=21, sharpe=-1.0)
    assert path.read_bytes() == original
    assert downstream == []


def test_t50_abort_precedes_every_prohibited_side_effect() -> None:
    source = _lifespan_source()
    abort = source.index("raise StartupSafetyAbort")
    for fragment in (
        "get_connection()",
        "build_api()",
        "fetch_account_summary",
        "run_reconciliation_once",
        "create_task(reconciliation_loop())",
        "create_task(health_snapshot_loop())",
        "create_task(telegram_inbound_loop())",
        "create_task(run_bot())",
        "start_telegram_control()",
    ):
        assert abort < source.index(fragment)

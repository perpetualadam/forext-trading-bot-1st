"""Isolated strategy-default and synthetic startup tests. No application lifespan."""

from __future__ import annotations

import ast
import json
import socket
import sys
from pathlib import Path

import pytest

from forex_bot.live_safety import (
    AUTH_BLOCKED,
    REASON_FUTURE_SCHEMA,
    SafetyStateProtected,
    _blank_document,
    assert_new_live_exposure_allowed,
    initialise_fail_closed,
    live_open_blocked_reason,
    live_order_auth_reason,
    live_order_auth_state,
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
_ACTIVE_AT_IMPORT = {name: strategies[name].active for name in STRATEGY_NAMES}


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


def _inactive_registry() -> None:
    assert live_order_auth_state() == AUTH_BLOCKED
    for name in STRATEGY_NAMES:
        assert strategies[name].active is False
        assert strategies[name].authorised_for_live is False


def test_t01_new_strategy_defaults_inactive() -> None:
    assert Strategy("synthetic").active is False


def test_t02_all_six_instances_default_inactive() -> None:
    assert set(STRATEGY_NAMES) == {
        "scalp",
        "trend",
        "mean_reversion",
        "swing_trend",
        "swing_mean_reversion",
        "swing_breakout",
    }
    assert _ACTIVE_AT_IMPORT == {name: False for name in STRATEGY_NAMES}
    assert all(Strategy(name).active is False for name in STRATEGY_NAMES)


def test_t03_explicit_false_remains_inactive() -> None:
    strategy = Strategy("scalp")
    strategy.active = False
    assert strategy.active is False


def test_t04_explicit_true_remains_supported() -> None:
    strategy = Strategy("scalp")
    strategy.active = True
    assert strategy.active is True


def test_t05_none_does_not_activate() -> None:
    strategy = Strategy("scalp")
    strategy.active = None
    assert strategy.active is False


def test_t06_string_true_does_not_activate() -> None:
    strategy = Strategy("scalp")
    strategy.active = "true"
    assert strategy.active is False


def test_t07_string_false_does_not_activate() -> None:
    strategy = Strategy("scalp")
    strategy.active = "false"
    assert strategy.active is False


def test_t08_numeric_one_does_not_activate() -> None:
    strategy = Strategy("scalp")
    strategy.active = 1
    assert strategy.active is False


def test_t09_numeric_zero_does_not_activate() -> None:
    strategy = Strategy("scalp")
    strategy.active = 0
    assert strategy.active is False


def test_t10_empty_collection_does_not_activate() -> None:
    strategy = Strategy("scalp")
    strategy.active = []
    assert strategy.active is False


def test_t11_nonempty_collection_does_not_activate() -> None:
    strategy = Strategy("scalp")
    strategy.active = ["scalp"]
    assert strategy.active is False


def test_t12_unknown_object_does_not_activate() -> None:
    strategy = Strategy("scalp")
    strategy.active = object()
    assert strategy.active is False


def test_t13_missing_activation_field_fails_closed() -> None:
    document = _blank_document(reason="operator_preflight_blocked")
    del document["strategies"]["scalp"]["active"]
    path = _write(json.dumps(document).encode("utf-8"))
    original = path.read_bytes()
    initialise_fail_closed()
    assert path.read_bytes() == original
    _inactive_registry()


def test_t14_invalid_persisted_activation_fails_closed() -> None:
    document = _blank_document(reason="operator_preflight_blocked")
    document["strategies"]["trend"]["active"] = "false"
    path = _write(json.dumps(document).encode("utf-8"))
    original = path.read_bytes()
    initialise_fail_closed()
    assert path.read_bytes() == original
    _inactive_registry()


def test_t15_corrupt_safety_state_fails_closed() -> None:
    path = _write(b"{not-json")
    initialise_fail_closed()
    assert path.read_bytes() == b"{not-json"
    _inactive_registry()


def test_t16_future_schema_fails_closed() -> None:
    original = b'{"schema_version": 2, "note": "synthetic"}\n'
    path = _write(original)
    initialise_fail_closed()
    assert path.read_bytes() == original
    assert live_order_auth_reason() == REASON_FUTURE_SCHEMA
    _inactive_registry()


def test_t17_blocked_authorisation_remains_blocked() -> None:
    document = _blank_document(reason="operator_preflight_blocked")
    _write(json.dumps(document).encode("utf-8"))
    initialise_fail_closed()
    assert live_order_auth_state() == AUTH_BLOCKED
    _inactive_registry()


def test_t18_construction_makes_no_broker_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def rejected(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("broker socket")

    monkeypatch.setattr(socket, "socket", rejected)
    built = [Strategy(name) for name in STRATEGY_NAMES]
    assert all(item.active is False for item in built)


def test_t19_construction_makes_no_database_calls() -> None:
    source = Path("forex_bot/strategy_meta.py").read_text(encoding="utf-8")
    assert "psycopg" not in source
    assert "get_connection" not in source
    assert all(Strategy(name).active is False for name in STRATEGY_NAMES)


def _synthetic_startup(payload: bytes | None) -> list[str]:
    """Model ordering only. This does not call the application lifespan."""
    trace = ["construct"]
    assert all(Strategy(name).active is False for name in STRATEGY_NAMES)
    trace.append("safety")
    if payload is not None:
        _write(payload)
    initialise_fail_closed()
    trace.append("safety_returned")
    return trace


def test_t20_synthetic_startup_validates_safety_before_activation() -> None:
    document = _blank_document(reason="operator_preflight_blocked")
    trace = _synthetic_startup(json.dumps(document).encode("utf-8"))
    assert trace.index("safety") < trace.index("safety_returned")
    _inactive_registry()


def test_t21_synthetic_startup_rejects_corrupt_state() -> None:
    path = _path()
    _synthetic_startup(b"{truncated")
    assert path.read_bytes() == b"{truncated"
    _inactive_registry()


def test_t22_synthetic_startup_rejects_future_schema() -> None:
    original = b'{"schema_version": 9}\n'
    path = _path()
    _synthetic_startup(original)
    assert path.read_bytes() == original
    _inactive_registry()


def test_t23_synthetic_startup_failure_does_not_activate() -> None:
    _synthetic_startup(b"")
    _inactive_registry()
    assert live_open_blocked_reason() is not None


def test_t24_synthetic_broker_stays_disabled_before_safety() -> None:
    broker: list[str] = []
    fresh = [Strategy(name) for name in STRATEGY_NAMES]
    assert all(strategy.active is False for strategy in fresh)
    _write(b"{bad")
    initialise_fail_closed()
    assert broker == []
    _inactive_registry()


def test_t25_synthetic_scheduler_stays_disabled_before_safety() -> None:
    scheduler: list[str] = []
    _write(b'{"schema_version": 3}')
    initialise_fail_closed()
    assert scheduler == []
    _inactive_registry()


def test_t26_synthetic_order_routing_stays_blocked() -> None:
    document = _blank_document(reason="operator_preflight_blocked")
    _write(json.dumps(document).encode("utf-8"))
    initialise_fail_closed()
    assert live_open_blocked_reason() is not None
    with pytest.raises(RuntimeError, match="LIVE_ORDER_AUTH"):
        assert_new_live_exposure_allowed(action="open")


def test_t27_legitimate_operator_activation_remains_supported() -> None:
    initialise_fail_closed()
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
        reason="synthetic_operator_clear",
        operator_confirmed=True,
    )
    assert strategies["scalp"].active is False
    assert live_order_auth_state() == AUTH_BLOCKED


def test_t28_unknown_field_preservation_still_works() -> None:
    document = _blank_document(reason="operator_preflight_blocked")
    document["future_metadata"] = {"preserve": True}
    document["strategies"]["mean_reversion"]["future_policy"] = {"mode": "synthetic"}
    _write(json.dumps(document).encode("utf-8"))
    initialise_fail_closed()
    loaded = json.loads(_path().read_text(encoding="utf-8"))
    assert loaded["future_metadata"] == {"preserve": True}
    assert loaded["strategies"]["mean_reversion"]["future_policy"] == {"mode": "synthetic"}
    _inactive_registry()


def test_t29_protected_file_behaviour_still_works() -> None:
    original = b'{"schema_version": 4, "keep": true}\n'
    path = _write(original)
    initialise_fail_closed()
    with pytest.raises(SafetyStateProtected):
        persist_evolve_disable("scalp", sample_count=21, sharpe=-1.0)
    assert path.read_bytes() == original
    _inactive_registry()


def test_t30_blocked_authorisation_round_trip() -> None:
    document = _blank_document(reason="operator_preflight_blocked")
    assert document["live_order_authorisation"]["state"] == AUTH_BLOCKED
    _write(json.dumps(document).encode("utf-8"))
    initialise_fail_closed()
    loaded = json.loads(_path().read_text(encoding="utf-8"))
    assert loaded["live_order_authorisation"]["state"] == AUTH_BLOCKED
    assert live_order_auth_state() == AUTH_BLOCKED


def test_t31_protected_exception_is_contained_by_synthetic_caller() -> None:
    original = b'{"schema_version": 5}\n'
    path = _write(original)
    initialise_fail_closed()

    def synthetic_evolve_caller() -> str:
        try:
            persist_evolve_disable("trend", sample_count=21, sharpe=-0.5)
        except SafetyStateProtected:
            return "contained"
        return "wrote"

    assert synthetic_evolve_caller() == "contained"
    assert path.read_bytes() == original
    assert strategies["trend"].active is False


def test_t32_no_production_operational_paths() -> None:
    text = str(_path())
    assert "data\\ops" not in text
    assert "v2_shadow" not in text
    assert "data/ops" not in text.replace("\\", "/")


def test_t33_no_network_socket_during_safety_load(monkeypatch: pytest.MonkeyPatch) -> None:
    def rejected(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network socket")

    monkeypatch.setattr(socket, "socket", rejected)
    document = _blank_document(reason="operator_preflight_blocked")
    _write(json.dumps(document).encode("utf-8"))
    initialise_fail_closed()
    _inactive_registry()


def test_t34_no_production_database_access() -> None:
    assert "forex_bot.database" not in sys.modules
    assert "psycopg2" not in sys.modules


def test_t35_application_lifespan_is_not_executed() -> None:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module != "forex_bot.app"
        if isinstance(node, ast.Import):
            assert all(alias.name != "forex_bot.app" for alias in node.names)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "lifespan"
    assert "forex_bot.app" not in sys.modules

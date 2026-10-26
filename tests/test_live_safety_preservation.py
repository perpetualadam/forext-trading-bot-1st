"""Isolated safety-state preservation tests. Synthetic files only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forex_bot.live_safety import (
    AUTH_BLOCKED,
    KNOWN_STRATEGY_NAMES,
    REASON_DEFAULT_DENY,
    REASON_FUTURE_SCHEMA,
    REASON_UNREADABLE,
    SafetyStateProtected,
    _blank_document,
    initialise_fail_closed,
    live_order_auth_reason,
    live_order_auth_state,
    operator_set_live_order_authorisation,
    persist_evolve_disable,
    reset_live_safety_for_tests,
    state_path,
)
from forex_bot.strategy_meta import strategies


def _path() -> Path:
    path = state_path()
    assert "data\\ops" not in str(path)
    assert "data/ops" not in str(path).replace("\\", "/")
    assert "v2_shadow" not in str(path)
    return path


def _valid_document() -> dict:
    document = _blank_document(reason="operator_preflight_blocked")
    for row in document["strategies"].values():
        row["active"] = False
        row["authorised_for_live"] = False
    return document


def _write_bytes(payload: bytes) -> Path:
    path = _path()
    path.write_bytes(payload)
    return path


def _write_json(document: dict) -> Path:
    return _write_bytes(json.dumps(document).encode("utf-8"))


def _inactive() -> None:
    assert live_order_auth_state() == AUTH_BLOCKED
    for name in KNOWN_STRATEGY_NAMES:
        assert strategies[name].active is False
        assert strategies[name].authorised_for_live is False


def test_t01_valid_blocked_state_loads() -> None:
    _write_json(_valid_document())
    initialise_fail_closed()
    _inactive()
    assert json.loads(_path().read_text(encoding="utf-8"))["schema_version"] == 1


def test_t02_valid_blocked_state_round_trips() -> None:
    _write_json(_valid_document())
    initialise_fail_closed()
    reset_live_safety_for_tests()
    initialise_fail_closed()
    _inactive()
    saved = json.loads(_path().read_text(encoding="utf-8"))
    assert saved["live_order_authorisation"]["state"] == AUTH_BLOCKED


def test_t03_unknown_top_level_scalar_survives() -> None:
    document = _valid_document()
    document["future_flag"] = 7
    _write_json(document)
    initialise_fail_closed()
    assert json.loads(_path().read_text(encoding="utf-8"))["future_flag"] == 7
    _inactive()


def test_t04_unknown_top_level_object_survives() -> None:
    document = _valid_document()
    document["future_metadata"] = {"created_by": "synthetic_test", "nested": {"preserve": True}}
    _write_json(document)
    initialise_fail_closed()
    saved = json.loads(_path().read_text(encoding="utf-8"))
    assert saved["future_metadata"] == document["future_metadata"]
    _inactive()


def test_t05_unknown_strategy_scalar_survives() -> None:
    document = _valid_document()
    document["strategies"]["scalp"]["future_note"] = "keep"
    _write_json(document)
    initialise_fail_closed()
    saved = json.loads(_path().read_text(encoding="utf-8"))
    assert saved["strategies"]["scalp"]["future_note"] == "keep"
    assert saved["strategies"]["scalp"]["active"] is False


def test_t06_unknown_strategy_object_survives() -> None:
    document = _valid_document()
    document["strategies"]["trend"]["future_policy"] = {"mode": "synthetic", "preserve": True}
    _write_json(document)
    initialise_fail_closed()
    saved = json.loads(_path().read_text(encoding="utf-8"))
    assert saved["strategies"]["trend"]["future_policy"] == {
        "mode": "synthetic",
        "preserve": True,
    }
    assert strategies["trend"].active is False


def test_t07_unknown_future_strategy_entry_survives() -> None:
    document = _valid_document()
    document["strategies"]["future_breakout"] = {
        "active": True,
        "note": "not a live strategy",
    }
    _write_json(document)
    initialise_fail_closed()
    saved = json.loads(_path().read_text(encoding="utf-8"))
    assert saved["strategies"]["future_breakout"]["note"] == "not a live strategy"
    assert "future_breakout" not in strategies
    _inactive()


def test_t08_unknown_metadata_cannot_enable_trading() -> None:
    document = _valid_document()
    document["trading_allowed"] = True
    document["strategies"]["scalp"]["future_policy"] = {"active": True}
    _write_json(document)
    initialise_fail_closed()
    _inactive()
    assert live_order_auth_state() == AUTH_BLOCKED


def test_t09_future_schema_is_not_overwritten() -> None:
    raw = b'{\n  "schema_version": 2,\n  "keep": true\n}\n'
    path = _write_bytes(raw)
    initialise_fail_closed()
    assert path.read_bytes() == raw
    _inactive()


def test_t10_future_schema_fails_closed() -> None:
    raw = b'{"schema_version": 9, "live_order_authorisation": {"state": "ALLOWED"}}\n'
    _write_bytes(raw)
    initialise_fail_closed()
    assert live_order_auth_state() == AUTH_BLOCKED
    assert live_order_auth_reason() == REASON_FUTURE_SCHEMA
    _inactive()


def test_t11_repeated_future_schema_reads_are_non_destructive() -> None:
    raw = b'{"schema_version": 3, "strategies": {"scalp": {"active": true}}}\n'
    path = _write_bytes(raw)
    for _ in range(3):
        reset_live_safety_for_tests()
        initialise_fail_closed()
        assert path.read_bytes() == raw
    with pytest.raises(SafetyStateProtected):
        persist_evolve_disable("scalp", sample_count=1, sharpe=0.0)
    with pytest.raises(SafetyStateProtected):
        operator_set_live_order_authorisation(
            state=AUTH_BLOCKED,
            reason="must-not-replace",
            operator_confirmed=True,
        )
    assert path.read_bytes() == raw


def test_t12_corrupt_json_is_not_overwritten() -> None:
    raw = b"{not-json"
    path = _write_bytes(raw)
    initialise_fail_closed()
    assert path.read_bytes() == raw
    _inactive()


def test_t13_truncated_json_fails_closed() -> None:
    raw = b'{"schema_version": 1, "live_order_authorisation":'
    path = _write_bytes(raw)
    initialise_fail_closed()
    assert path.read_bytes() == raw
    assert live_order_auth_state() == AUTH_BLOCKED


def test_t14_non_object_root_fails_closed() -> None:
    raw = b"[1, 2, 3]"
    path = _write_bytes(raw)
    initialise_fail_closed()
    assert path.read_bytes() == raw
    _inactive()


def test_t15_invalid_schema_version_type_fails_closed() -> None:
    document = _valid_document()
    document["schema_version"] = "1"
    raw = json.dumps(document).encode("utf-8")
    path = _write_bytes(raw)
    initialise_fail_closed()
    assert path.read_bytes() == raw
    _inactive()


def test_t16_invalid_authorisation_fails_closed() -> None:
    document = _valid_document()
    document["live_order_authorisation"]["state"] = "YES"
    raw = json.dumps(document).encode("utf-8")
    path = _write_bytes(raw)
    initialise_fail_closed()
    assert path.read_bytes() == raw
    assert live_order_auth_state() == AUTH_BLOCKED


def test_t17_invalid_activation_value_fails_closed() -> None:
    document = _valid_document()
    document["strategies"]["scalp"]["active"] = "false"
    raw = json.dumps(document).encode("utf-8")
    path = _write_bytes(raw)
    initialise_fail_closed()
    assert path.read_bytes() == raw
    assert strategies["scalp"].active is False


def test_t18_missing_activation_value_fails_closed() -> None:
    document = _valid_document()
    del document["strategies"]["mean_reversion"]["active"]
    raw = json.dumps(document).encode("utf-8")
    path = _write_bytes(raw)
    initialise_fail_closed()
    assert path.read_bytes() == raw
    assert strategies["mean_reversion"].active is False


def test_t19_missing_file_creates_only_blocked_state() -> None:
    path = _path()
    assert not path.exists()
    initialise_fail_closed()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["live_order_authorisation"]["state"] == AUTH_BLOCKED
    assert live_order_auth_reason() == REASON_DEFAULT_DENY
    _inactive()
    assert not path.with_suffix(path.suffix + ".tmp").exists()


def test_t20_permission_failure_is_not_a_missing_file(monkeypatch) -> None:
    raw = b'{"schema_version": 2}\n'
    path = _write_bytes(raw)

    def denied(_path: Path) -> str:
        raise PermissionError("synthetic denial")

    monkeypatch.setattr("forex_bot.live_safety._read_text", denied)
    initialise_fail_closed()
    assert path.read_bytes() == raw
    assert live_order_auth_reason() == REASON_UNREADABLE
    assert live_order_auth_reason() != REASON_DEFAULT_DENY
    _inactive()


def test_t21_successful_replacement_preserves_valid_json() -> None:
    initialise_fail_closed()
    path = _path()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["schema_version"] == 1
    assert saved["live_order_authorisation"]["state"] == AUTH_BLOCKED
    assert not path.with_suffix(path.suffix + ".tmp").exists()


def test_t22_serialization_failure_preserves_original(monkeypatch) -> None:
    path = _write_json(_valid_document())
    original = path.read_bytes()

    def broken(_payload: dict) -> str:
        raise TypeError("synthetic serialize failure")

    monkeypatch.setattr("forex_bot.live_safety._render_payload", broken)
    with pytest.raises(TypeError):
        initialise_fail_closed()
    assert path.read_bytes() == original


def test_t23_temporary_write_failure_preserves_original(monkeypatch) -> None:
    path = _write_json(_valid_document())
    original = path.read_bytes()
    real_open = Path.open

    def guarded(self: Path, *args, **kwargs):
        if str(self).endswith(".json.tmp"):
            raise OSError("synthetic temp failure")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    initialise_fail_closed()
    assert path.read_bytes() == original
    assert live_order_auth_state() == AUTH_BLOCKED


def test_t24_replace_failure_preserves_original(monkeypatch) -> None:
    path = _write_json(_valid_document())
    original = path.read_bytes()

    def boom(*_args, **_kwargs) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr("forex_bot.live_safety.os.replace", boom)
    initialise_fail_closed()
    assert path.read_bytes() == original
    assert live_order_auth_state() == AUTH_BLOCKED


def test_t25_failed_save_leaves_no_partial_target(monkeypatch) -> None:
    path = _write_json(_valid_document())
    original = path.read_bytes()

    def boom(*_args, **_kwargs) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr("forex_bot.live_safety.os.replace", boom)
    initialise_fail_closed()
    assert path.read_bytes() == original
    assert json.loads(original.decode("utf-8"))["schema_version"] == 1
    assert not path.with_suffix(path.suffix + ".tmp").exists()


def test_t26_blocked_authorisation_remains_blocked() -> None:
    document = _valid_document()
    document["marker"] = "stay-blocked"
    _write_json(document)
    initialise_fail_closed()
    saved = json.loads(_path().read_text(encoding="utf-8"))
    assert saved["live_order_authorisation"]["state"] == AUTH_BLOCKED
    assert saved["marker"] == "stay-blocked"
    assert live_order_auth_state() == AUTH_BLOCKED


def test_t27_recovery_never_creates_allowed_authorisation() -> None:
    initialise_fail_closed()
    created = json.loads(_path().read_text(encoding="utf-8"))
    assert created["live_order_authorisation"]["state"] == AUTH_BLOCKED
    _path().write_bytes(b"{not-json")
    reset_live_safety_for_tests()
    initialise_fail_closed()
    assert live_order_auth_state() == AUTH_BLOCKED
    assert _path().read_bytes() == b"{not-json"


def test_t28_safe_defaults_leave_six_strategies_inactive() -> None:
    assert not _path().exists()
    initialise_fail_closed()
    assert set(KNOWN_STRATEGY_NAMES) == {
        "scalp",
        "trend",
        "mean_reversion",
        "swing_trend",
        "swing_mean_reversion",
        "swing_breakout",
    }
    _inactive()


def test_t29_tested_module_has_no_broker_or_database_client() -> None:
    source = Path("forex_bot/live_safety.py").read_text(encoding="utf-8").lower()
    for banned in ("oanda", "psycopg", "socket", "requests", "urllib", "httpx"):
        assert banned not in source


def test_t30_existing_valid_document_remains_compatible() -> None:
    document = _blank_document(reason="operator_preflight_blocked")
    _write_json(document)
    initialise_fail_closed()
    saved = json.loads(_path().read_text(encoding="utf-8"))
    assert saved["schema_version"] == 1
    assert saved["live_order_authorisation"]["state"] == AUTH_BLOCKED
    assert set(KNOWN_STRATEGY_NAMES) <= set(saved["strategies"])
    _inactive()

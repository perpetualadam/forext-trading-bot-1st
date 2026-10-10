"""Isolated fail-closed live-order gate and durable strategy state. No broker I/O."""

from __future__ import annotations

import json
import logging
import threading
from unittest.mock import patch

import pytest

from forex_bot.bot_loop import evolve
from forex_bot.decision_skip_log import LIVE_ORDER_AUTH_BLOCKED, log_decision_skip
from forex_bot.execution import (
    halt_trading,
    pre_trade_entry_allowed,
    pre_trade_entry_blocked_reason,
    resume_trading,
)
from forex_bot.live_safety import (
    AUTH_ALLOWED,
    AUTH_BLOCKED,
    KNOWN_STRATEGY_NAMES,
    REASON_EVOLVE,
    REASON_PERSISTED_ALLOWED_IGNORED,
    assert_new_live_exposure_allowed,
    initialise_fail_closed,
    live_open_blocked_reason,
    live_order_auth_state,
    live_safety_snapshot,
    operator_set_live_order_authorisation,
    operator_set_strategy_active,
    persist_evolve_disable,
    persisted_live_order_auth_state,
    reset_live_safety_for_tests,
    state_path,
)
from forex_bot.log_config import configure_forex_bot_logging
from forex_bot.oanda_exec import (
    _place_market_order_open_sync,
    assert_broker_order_allowed,
)
from forex_bot.strategy_meta import strategies
from forex_bot.telegram_control import cmd_system


def _negative_pnl(n: int = 20) -> list[float]:
    return [-1.0] * n


def test_fresh_process_with_no_persisted_state_blocks_live_opens():
    assert not state_path().is_file()
    initialise_fail_closed()
    assert live_order_auth_state() == AUTH_BLOCKED
    assert live_open_blocked_reason() == "live_order_auth_blocked"
    assert pre_trade_entry_allowed() is False
    assert pre_trade_entry_blocked_reason() == "live_order_auth_blocked"
    for name in KNOWN_STRATEGY_NAMES:
        strat = strategies[name]
        assert strat.active is False
        assert strat.authorised_for_live is False
    with pytest.raises(RuntimeError, match="LIVE_ORDER_AUTH"):
        assert_new_live_exposure_allowed(action="open")


def test_missing_and_corrupt_persistence_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("USE_OANDA_LIVE", "true")
    initialise_fail_closed()
    path = state_path()
    path.write_text("{not-json", encoding="utf-8")
    reset_live_safety_for_tests()
    for strat in strategies.values():
        strat.active = True
        strat.authorised_for_live = True
    initialise_fail_closed()
    assert live_order_auth_state() == AUTH_BLOCKED
    assert all(s.active is False and s.authorised_for_live is False for s in strategies.values())
    with pytest.raises(RuntimeError, match="LIVE_ORDER_AUTH"):
        assert_broker_order_allowed(execution_kind="live", action="open")


def test_all_six_remain_disabled_after_simulated_restart():
    initialise_fail_closed()
    for name in KNOWN_STRATEGY_NAMES:
        persist_evolve_disable(name, sample_count=21, sharpe=-0.4)
    for strat in strategies.values():
        strat.active = True
        strat.authorised_for_live = True
    reset_live_safety_for_tests()
    initialise_fail_closed()
    assert live_order_auth_state() == AUTH_BLOCKED
    for name in KNOWN_STRATEGY_NAMES:
        strat = strategies[name]
        assert strat.active is False
        assert strat.authorised_for_live is False
        assert strat.disable_reason == REASON_EVOLVE
        assert strat.loaded_from_durable is True


def test_negative_sharpe_after_20_samples_disables_and_persists():
    initialise_fail_closed()
    target = strategies["mean_reversion"]
    target.active = True
    target.pnl[:] = _negative_pnl(20)
    evolve()
    assert target.active is False
    assert target.disable_reason == REASON_EVOLVE
    blob = json.loads(state_path().read_text(encoding="utf-8"))
    row = blob["strategies"]["mean_reversion"]
    assert row["active"] is False
    assert row["disable_reason"] == REASON_EVOLVE
    assert row["sample_count"] >= 20
    assert float(row["sharpe"]) < 0


def test_restart_never_silently_reactivates(monkeypatch):
    initialise_fail_closed()
    persist_evolve_disable("trend", sample_count=22, sharpe=-0.2)
    strategies["trend"].active = True
    reset_live_safety_for_tests()
    initialise_fail_closed()
    assert strategies["trend"].active is False
    assert strategies["trend"].authorised_for_live is False
    with pytest.raises(PermissionError):
        operator_set_strategy_active(
            name="trend", active=True, reason="nope", operator_confirmed=False
        )
    assert strategies["trend"].active is False


def test_diagnostics_report_flags_and_sharpe():
    initialise_fail_closed()
    strategies["scalp"].pnl[:] = _negative_pnl(20)
    persist_evolve_disable("scalp", sample_count=20, sharpe=float(strategies["scalp"].sharpe()))
    snap = live_safety_snapshot()
    assert snap["live_order_authorisation"] == AUTH_BLOCKED
    assert snap["strategy_state_initialised"] is True
    names = {row["name"]: row for row in snap["strategies"]}
    assert set(names) >= set(KNOWN_STRATEGY_NAMES)
    scalp = names["scalp"]
    assert scalp["active"] is False
    assert scalp["pnl_n"] == 20
    assert scalp["sharpe"] < 0
    assert scalp["disable_reason"] == REASON_EVOLVE
    assert scalp["loaded_from_durable"] is True
    from forex_bot.app import _system_snapshot

    system = _system_snapshot()
    assert system["live_order_authorisation"] == AUTH_BLOCKED
    assert "strategies" in system
    text = cmd_system().text
    assert "live_order_auth=BLOCKED" in text
    assert "scalp" in text
    assert "OANDA_ACCESS_TOKEN" not in text


def test_blocked_open_sends_no_broker_request(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("USE_OANDA_LIVE", "true")
    initialise_fail_closed()
    calls: list = []

    class FakeAPI:
        def request(self, r):
            calls.append(r)
            raise AssertionError("must not reach OANDA")

    with (
        patch("forex_bot.oanda_exec.get_api", return_value=FakeAPI()),
        patch("forex_bot.oanda_exec._account_id", return_value="ACC"),
        pytest.raises(RuntimeError, match="LIVE_ORDER_AUTH"),
    ):
        _place_market_order_open_sync("EUR_USD", 2.0, "BUY", "cid-block")
    assert calls == []


def test_every_live_open_path_respects_default_deny(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("USE_OANDA_LIVE", "true")
    with pytest.raises(RuntimeError, match="LIVE_ORDER_AUTH"):
        assert_broker_order_allowed(execution_kind="live", action="open")
    initialise_fail_closed()
    with pytest.raises(RuntimeError, match="LIVE_ORDER_AUTH"):
        assert_broker_order_allowed(execution_kind="live", action="open")
    assert_broker_order_allowed(execution_kind="live", action="close")


def test_concurrent_opens_cannot_bypass_gate(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("USE_OANDA_LIVE", "true")
    initialise_fail_closed()
    errors: list[str] = []
    calls = {"n": 0}

    class FakeAPI:
        def request(self, r):
            calls["n"] += 1
            return {}

    def worker():
        try:
            with patch("forex_bot.oanda_exec.get_api", return_value=FakeAPI()):
                _place_market_order_open_sync("EUR_USD", 1.0, "BUY", "cid-race")
            errors.append("opened")
        except RuntimeError as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=worker) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert calls["n"] == 0
    assert all("LIVE_ORDER_AUTH" in msg for msg in errors)
    assert len(errors) == 12


def test_kill_switch_and_halt_still_block_when_auth_allowed(monkeypatch, allow_live_order_create):
    monkeypatch.setenv("KILL_SWITCH", "true")
    assert pre_trade_entry_blocked_reason() == "kill_switch_env"
    monkeypatch.delenv("KILL_SWITCH", raising=False)
    halt_trading()
    try:
        assert pre_trade_entry_blocked_reason() == "halt_runtime"
    finally:
        resume_trading()
    assert live_order_auth_state() == AUTH_ALLOWED
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("USE_OANDA_LIVE", "true")
    assert_broker_order_allowed(execution_kind="live", action="open")


def test_close_allowed_while_new_opens_blocked(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "live_broker")
    monkeypatch.setenv("USE_OANDA_LIVE", "true")
    initialise_fail_closed()
    assert_new_live_exposure_allowed(action="close")
    assert_broker_order_allowed(execution_kind="live", action="close")
    with pytest.raises(RuntimeError, match="LIVE_ORDER_AUTH"):
        assert_broker_order_allowed(execution_kind="live", action="open")


def test_logging_skip_reasons_without_credentials(monkeypatch, caplog):
    secret = "oanda-secret-token-xyz12345"
    monkeypatch.setattr("forex_bot.config.Config.OANDA_ACCESS_TOKEN", secret)
    configure_forex_bot_logging()
    with caplog.at_level(logging.INFO, logger="forex_bot.decision_skip_log"):
        log_decision_skip(
            symbol="EUR_USD",
            reason=LIVE_ORDER_AUTH_BLOCKED,
            stage="pretrade",
            token=secret,
        )
    text = caplog.text
    assert LIVE_ORDER_AUTH_BLOCKED in text
    assert secret not in text
    assert "<redacted>" in text


def test_uvicorn_logging_configuration_emits_forex_bot_info(caplog):
    configure_forex_bot_logging()
    log = logging.getLogger("forex_bot")
    assert log.level <= logging.INFO
    with caplog.at_level(logging.INFO, logger="forex_bot.decision_skip_log"):
        log_decision_skip(symbol="GBP_USD", reason=LIVE_ORDER_AUTH_BLOCKED, stage="pretrade")
    assert LIVE_ORDER_AUTH_BLOCKED in caplog.text


def test_persist_failure_fails_closed(monkeypatch):
    from forex_bot import live_safety as ls

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(ls, "_atomic_write", boom)
    ls.initialise_fail_closed()
    assert ls.live_order_auth_state() == AUTH_BLOCKED
    assert ls.live_open_blocked_reason() is not None
    with pytest.raises(RuntimeError, match="LIVE_ORDER_AUTH"):
        ls.assert_new_live_exposure_allowed(action="open")


def test_operator_reactivation_requires_confirmation():
    initialise_fail_closed()
    with pytest.raises(PermissionError):
        operator_set_live_order_authorisation(
            state=AUTH_ALLOWED, reason="review", operator_confirmed=False
        )
    assert live_order_auth_state() == AUTH_BLOCKED
    operator_set_live_order_authorisation(
        state=AUTH_ALLOWED, reason="operator_review_complete", operator_confirmed=True
    )
    assert live_order_auth_state() == AUTH_ALLOWED
    operator_set_live_order_authorisation(
        state=AUTH_BLOCKED, reason="remain_blocked_for_deploy", operator_confirmed=True
    )
    assert live_order_auth_state() == AUTH_BLOCKED


def test_persisted_allowed_starts_effective_blocked():
    initialise_fail_closed()
    operator_set_live_order_authorisation(
        state=AUTH_ALLOWED, reason="previous_process", operator_confirmed=True
    )
    assert live_order_auth_state() == AUTH_ALLOWED
    assert persisted_live_order_auth_state() == AUTH_ALLOWED
    reset_live_safety_for_tests()
    initialise_fail_closed()
    assert live_order_auth_state() == AUTH_BLOCKED
    assert persisted_live_order_auth_state() == AUTH_ALLOWED
    assert live_open_blocked_reason() == "live_order_auth_blocked"
    snap = live_safety_snapshot()
    assert snap["effective_runtime_authorisation"] == AUTH_BLOCKED
    assert snap["persisted_authorisation"] == AUTH_ALLOWED
    assert snap["effective_runtime_authorisation_reason"] == REASON_PERSISTED_ALLOWED_IGNORED
    with pytest.raises(RuntimeError, match="LIVE_ORDER_AUTH"):
        assert_new_live_exposure_allowed(action="open")


def test_persisted_blocked_restores_blocked():
    initialise_fail_closed()
    reset_live_safety_for_tests()
    initialise_fail_closed()
    assert live_order_auth_state() == AUTH_BLOCKED
    assert persisted_live_order_auth_state() == AUTH_BLOCKED


def test_no_production_test_auth_helper():
    import forex_bot.live_safety as ls

    assert not hasattr(ls, "authorise_new_live_exposure_for_tests")


def test_test_helpers_refuse_outside_pytest(monkeypatch):
    import forex_bot.live_safety as ls

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with pytest.raises(RuntimeError, match="refused outside pytest"):
        ls.reset_live_safety_for_tests()
    with pytest.raises(RuntimeError, match="refused outside pytest"):
        ls.restore_strategy_runtime_defaults_for_tests()


def test_http_and_telegram_cannot_authorise():
    initialise_fail_closed()
    from forex_bot.execution import resume_trading
    from forex_bot.telegram_control import cmd_start_trading, cmd_stop

    try:
        cmd_stop()
        cmd_start_trading()
        assert live_order_auth_state() == AUTH_BLOCKED
    finally:
        resume_trading()
    from forex_bot.app import app

    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        src = getattr(endpoint, "__name__", "")
        assert "operator_set_live_order_authorisation" not in src
        assert "AUTH_ALLOWED" not in src


def test_lifespan_initialises_before_background_tasks():
    import inspect

    from forex_bot import app as appmod

    src = inspect.getsource(appmod.lifespan)
    assert src.index("initialise_fail_closed") < src.index("create_task(run_bot())")
    assert src.index("initialise_fail_closed") < src.index("create_task(reconciliation_loop())")
    assert "operator_set_live_order_authorisation" not in src


def test_preflight_inspect_and_write_refuses_overwrite(tmp_path):
    from forex_bot.live_safety_preflight import (
        inspect_safety_state_file,
        write_blocked_startup_document,
    )

    missing = tmp_path / "absent.json"
    report = inspect_safety_state_file(missing)
    assert report["present"] is False
    assert report["safe_for_trading_disabled_startup"] is True
    created = write_blocked_startup_document(missing)
    blob = json.loads(created.read_text(encoding="utf-8"))
    assert blob["live_order_authorisation"]["state"] == AUTH_BLOCKED
    with pytest.raises(FileExistsError):
        write_blocked_startup_document(missing)
    valid = inspect_safety_state_file(missing)
    assert valid["structurally_valid"] is True
    assert valid["persisted_authorisation"] == AUTH_BLOCKED
    assert valid["any_strategy_authorised_for_live"] is False


def test_no_http_route_enables_live_order_auth():
    from forex_bot.app import app

    paths = []
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        paths.append((path, methods))
        joined = " ".join(methods) + " " + path
        assert "live_order" not in joined.lower()
        assert "authoris" not in joined.lower()
    post_paths = {p for p, m in paths if "POST" in m}
    assert "/halt" in post_paths
    assert "/resume" in post_paths

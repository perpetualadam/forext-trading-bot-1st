"""Default test env: do not inherit local .env live/notional overrides."""

from __future__ import annotations

import pytest


@pytest.fixture
def historical_packaging_root(tmp_path):
    """Reconstruct G.13 from verified G.10 bytes, never today's working tree."""
    import hashlib
    import importlib.util
    import json
    import shutil
    import tarfile
    from pathlib import Path, PurePosixPath

    repo = Path(__file__).resolve().parents[1]
    archive = repo / "data/research/adaptive_ensemble/g10/source_snapshot.tar"
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == "d0317de858a00b194bc44408932ad6508eec411fe0179b0196175a2985b12277"
    root = tmp_path / "historical"
    root.mkdir()
    with tarfile.open(archive, "r:") as source:
        for member in source:
            rel = PurePosixPath(member.name)
            assert member.isfile() and not rel.is_absolute() and ".." not in rel.parts
            target = root.joinpath(*rel.parts)
            assert target.resolve().is_relative_to(root.resolve())
            target.parent.mkdir(parents=True, exist_ok=True)
            handle = source.extractfile(member)
            assert handle is not None
            target.write_bytes(handle.read())
    spec = importlib.util.spec_from_file_location("historical_g13_render", repo / "tests/g13_packaging.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    allow = json.loads((repo / "data/research/adaptive_ensemble/g10/production_allowlist.json").read_text())
    (root / "Dockerfile").write_bytes(helper.render_dockerfile(helper.allowlist_paths(allow)).encode())
    assert hashlib.sha256((root / "Dockerfile").read_bytes()).hexdigest() == "4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad"
    for rel in ("data/research/adaptive_ensemble/g7/source_snapshot.tar", "data/research/adaptive_ensemble/g7/manifest.json"):
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / rel, target)
    return root


@pytest.fixture
def historical_staging_root(historical_packaging_root, tmp_path):
    import json
    import shutil
    from pathlib import Path
    repo = Path(__file__).resolve().parents[1]
    allow = json.loads((repo / "data/research/adaptive_ensemble/g10/production_allowlist.json").read_text())
    stage = tmp_path / "staged"
    stage.mkdir()
    for row in allow["files"]:
        target = stage / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(historical_packaging_root / row["path"], target)
    return stage

# These modules install a process-wide network barrier during import, or they
# refuse to import unless that barrier is already installed. Stage runners
# execute them. The shared CI process must not import them.
collect_ignore = [
    "test_r10_offline_startup.py",
    "test_r11_historical_recovery.py",
    "test_r26_broker_reconciliation.py",
    "test_r27_oanda_account_contract.py",
    "test_r29_scalp_readiness.py",
    "test_r30_scalp_lifecycle.py",
    "test_r31_strategy_screening.py",
    "test_r32_signal_diagnostics.py",
    "test_r33_ai_rl_audit.py",
    "test_r34_stub_removal.py",
]


@pytest.fixture(autouse=True)
def _isolate_sizing_env(monkeypatch):
    monkeypatch.delenv("POSITION_NOTIONAL_PCT_OF_NAV", raising=False)
    monkeypatch.delenv("MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV", raising=False)
    monkeypatch.delenv("MAX_GROSS_USD_NOTIONAL", raising=False)
    monkeypatch.delenv("POSITION_RISK_PCT", raising=False)
    monkeypatch.delenv("POSITION_RISK_PCT_MAX", raising=False)
    monkeypatch.delenv("MIN_STOP_DISTANCE_PRICE", raising=False)
    monkeypatch.delenv("FX_SESSION_ALWAYS", raising=False)
    monkeypatch.delenv("FOREX_SYMBOLS", raising=False)
    monkeypatch.delenv("MAX_SAME_USD_DIRECTION_POSITIONS", raising=False)
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    monkeypatch.setenv("PAPER_TRADING", "true")
    monkeypatch.setenv("USE_OANDA_LIVE", "false")
    monkeypatch.setenv("TELEGRAM_COMMANDS", "false")
    monkeypatch.setenv("TELEGRAM_INBOUND", "0")
    monkeypatch.setenv("DECISION_SKIP_LOG_INTERVAL_SEC", "0")


@pytest.fixture(autouse=True)
def _isolate_live_safety(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_SAFETY_STATE_PATH", str(tmp_path / "live_safety_state.json"))
    monkeypatch.setenv("DECISION_REPAIR_SELECT_CURSOR_PATH", str(tmp_path / "select_cursor.json"))
    monkeypatch.setenv("DECISION_REPAIR_RISK_PATH", str(tmp_path / "account_risk.json"))
    monkeypatch.setenv("DECISION_REPAIR_AUDIT_PATH", str(tmp_path / "decisions.jsonl"))
    from forex_bot.decision_skip_log import reset_skip_log_for_tests
    from forex_bot.live_safety import (
        reset_live_safety_for_tests,
        restore_strategy_runtime_defaults_for_tests,
    )
    from forex_bot.strategy_meta import strategies

    reset_live_safety_for_tests()
    reset_skip_log_for_tests()
    restore_strategy_runtime_defaults_for_tests()
    # The legacy helper predates inactive defaults. Each test must explicitly
    # activate its own synthetic strategy; collection order must grant nothing.
    for strat in strategies.values():
        strat.active = False
    pnl_before = {name: list(strat.pnl) for name, strat in strategies.items()}
    yield
    reset_live_safety_for_tests()
    reset_skip_log_for_tests()
    restore_strategy_runtime_defaults_for_tests()
    for name, strat in strategies.items():
        strat.active = False
        if name in pnl_before:
            strat.pnl[:] = pnl_before[name]


@pytest.fixture
def allow_live_order_create():
    """Process-lifetime operator grant via the real API. Not a production HTTP/Telegram path."""
    from forex_bot.live_safety import (
        AUTH_ALLOWED,
        initialise_fail_closed,
        operator_set_live_order_authorisation,
    )

    initialise_fail_closed()
    operator_set_live_order_authorisation(
        state=AUTH_ALLOWED,
        reason="pytest_process_lifetime_operator",
        operator_confirmed=True,
    )


@pytest.fixture
def synthetic_journal(tmp_path, monkeypatch):
    """Real disposable journal and recovery fence; no operator live-order grant."""
    from forex_bot.close_journal import bootstrap_journal, active_journal, reset_journal_process_state
    from forex_bot.config import Config
    from forex_bot.startup_recovery import (
        execute_startup_sequence, live_management_permitted, reset_startup_recovery_memory,
    )
    reset_startup_recovery_memory()
    reset_journal_process_state()
    monkeypatch.setenv("CLOSE_JOURNAL_PATH", str(tmp_path / "synthetic-journal.sqlite"))
    monkeypatch.setattr(Config, "OANDA_ACCOUNT_ID", "ACC")
    bootstrap_journal(tmp_path / "synthetic-journal.sqlite", acknowledge_empty=True).close()
    report = execute_startup_sequence({"snapshot": "COMPLETE_EMPTY", "trades": []})
    assert report["state"] == "RECOVERY_COMPLETED"
    assert live_management_permitted()
    try:
        yield active_journal()
    finally:
        reset_startup_recovery_memory()
        reset_journal_process_state()
        from forex_bot.positions import positions
        positions.clear()


@pytest.fixture
def entry_intent_factory(synthetic_journal):
    """Reserve genuine one-shot intents only in the synthetic journal."""
    from decimal import Decimal
    from uuid import uuid4
    from forex_bot.close_journal import account_binding
    from forex_bot.entry_journal import begin_entry_submission

    def create(symbol="EUR_USD", units=2, direction="BUY", client_order_id="cid-x",
               stop_loss="1.09900", take_profit="1.10200"):
        return begin_entry_submission(
            account_binding_value=account_binding("ACC"), instrument=symbol,
            direction=direction, requested_units=Decimal(str(units)),
            position_instance_id=uuid4().hex, position_generation=1,
            client_order_id=client_order_id, strategy_name="scalp",
            stop_loss=stop_loss, take_profit=take_profit,
            entry_reference="1.10000", atr_at_entry_pips=None,
        )
    return create


@pytest.fixture
def close_intent_factory(synthetic_journal):
    from uuid import uuid4
    from forex_bot.close_journal import account_binding

    def create(symbol="EUR_USD", units=1, direction="BUY"):
        row = synthetic_journal.reserve(
            account_binding_value=account_binding("ACC"),
            position_instance_id=uuid4().hex, position_generation=1,
            instrument=symbol, trade_id=uuid4().hex, direction=direction,
            original_units=str(units), requested_units=str(units),
        )
        token = synthetic_journal.commit_submission_intent(row["operation_id"])
        return synthetic_journal.issue_submission_permit(row["operation_id"], token)
    return create


@pytest.fixture
def managed_close_transport(monkeypatch, synthetic_journal):
    """Fake HTTP only; exercise real close verification, persistence and deletion."""
    from uuid import uuid4
    from forex_bot import positions as posmod
    from forex_bot.broker_close_evidence import reset_close_evidence_state
    from forex_bot.close_journal import account_binding
    from forex_bot.position_recovery import persist_bot_position

    close_confirmed = posmod.close_confirmed_live_position

    def install(book, seen, error=None, *, with_kwargs=False):
        posmod.positions.clear()
        reset_close_evidence_state()
        for symbol, pos in book.items():
            if not isinstance(pos, posmod.Position):
                continue
            if pos.execution_kind == "live":
                if not pos.broker_trade_ids:
                    pos.broker_trade_ids = uuid4().hex
                posmod.open_position(pos)
                persist_bot_position(pos, account_binding("ACC"))
            else:
                posmod.open_position(pos)
        transactions = {}

        class API:
            def request(self, request):
                endpoint = str(request._endpoint)
                if "transactions/" in endpoint:
                    return {"transaction": transactions[endpoint.rsplit("/", 1)[-1]]}
                assert endpoint.endswith("/close"), endpoint
                symbol = next(symbol for symbol in book if f"/{symbol}/close" in endpoint)
                pos = book[symbol]
                args = (symbol, pos.strategy_name, pos.direction, pos.units,
                        pos.entry_price, pos.stop_loss, pos.take_profit)
                if isinstance(seen, dict):
                    seen["execute"] += 1
                else:
                    seen.execute.append((args, {"execution_kind": "live"}) if with_kwargs else args)
                failure = error(symbol) if callable(error) else error
                if failure is not None:
                    raise failure
                units = str(-abs(pos.units) if pos.direction == "BUY" else abs(pos.units))
                transaction_id = str(uuid4().int)
                tx = {
                    "id": transaction_id, "type": "ORDER_FILL", "accountID": "ACC",
                    "instrument": symbol, "units": units, "price": str(pos.entry_price),
                    "pl": "0", "time": "2026-10-01T12:00:00Z",
                    "reason": "MARKET_ORDER_POSITION_CLOSEOUT",
                    "tradesClosed": [{"tradeID": pos.broker_trade_ids, "units": units, "realizedPL": "0"}],
                }
                transactions[transaction_id] = tx
                side = "longOrderFillTransaction" if pos.direction == "BUY" else "shortOrderFillTransaction"
                return {side: tx, "relatedTransactionIDs": [transaction_id]}

        api = API()
        monkeypatch.setenv("EXECUTION_MODE", "live_broker")
        monkeypatch.setattr("forex_bot.oanda_exec.get_api", lambda: api)
        monkeypatch.setattr("forex_bot.oanda_client.get_api", lambda: api)
        monkeypatch.setattr("forex_bot.oanda_exec._account_id", lambda: "ACC")
        monkeypatch.setattr("forex_bot.oanda_rate_limit.acquire_oanda_rest_slot", lambda: None)
        # This suite injects management quotes and protection decisions itself.
        monkeypatch.setattr("forex_bot.broker_protection.record_management_protection_evidence", lambda _pos: None)

        def record_delete(symbol, operation):
            removed = close_confirmed(symbol, operation)
            if removed is not None:
                if isinstance(seen, dict):
                    seen["closed"] += 1
                else:
                    seen.closed.append(symbol)
            return removed
        monkeypatch.setattr(posmod, "close_confirmed_live_position", record_delete)
    return install

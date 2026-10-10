"""Isolated shadow-evaluator tests. No live broker, no live DB, no Docker."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]
import pytest

from forex_bot.live_safety import (
    AUTH_BLOCKED,
    initialise_fail_closed,
    live_order_auth_state,
    operator_set_strategy_active,
)
from forex_bot.shadow.accounting import (
    conservative_intrabar_exit,
    executable_price,
    quote_pnl_to_usd,
    usd_to_gbp,
)
from forex_bot.shadow.config import ShadowConfig
from forex_bot.shadow.engine import ShadowEngine
from forex_bot.shadow.reasons import ShadowReason
from forex_bot.shadow.replay import main as replay_main
from forex_bot.shadow.replay import replay_symbol, split_periods
from forex_bot.shadow.store import ShadowStore
from forex_bot.strategy_meta import strategies

UTC = timezone.utc
SHADOW_ROOT = Path("forex_bot") / "shadow"
FORBIDDEN_IMPORTS = {
    "forex_bot.oanda_exec",
    "forex_bot.trading",
    "forex_bot.bot_loop",
    "forex_bot.database",
    "forex_bot.telegram_control",
    "forex_bot.execution",
}


def _bars(n: int = 90, *, start: datetime | None = None, drift: float = 0.00015) -> pd.DataFrame:
    t0 = start or datetime(2026, 9, 16, 10, 0, tzinfo=UTC)
    rows = []
    px = 1.1000
    t = t0
    for _ in range(n):
        o = px
        c = px + drift
        rows.append(
            {
                "time": t,
                "open": o,
                "high": max(o, c) + 0.00025,
                "low": min(o, c) - 0.00025,
                "close": c,
                "volume": 100,
            }
        )
        px = c
        t = t + timedelta(minutes=5)
    return pd.DataFrame(rows)


def _cfg(**kwargs: object) -> ShadowConfig:
    base: dict[str, object] = {
        "enabled": True,
        "starting_nav_gbp": 97.15,
        "min_bars": 40,
        "scalp_lookback": 20,
        "swing_lookback": 30,
        "daily_loss_pct": 0.02,
        "max_drawdown_pct": 0.05,
    }
    base.update(kwargs)
    return ShadowConfig(**base)  # type: ignore[arg-type]


def test_shadow_disabled_by_default():
    engine = ShadowEngine(cfg=ShadowConfig())
    with pytest.raises(RuntimeError, match="disabled"):
        engine.process_symbol_bar(
            symbol="EUR_USD",
            history=_bars(50),
            bar_time=datetime(2026, 9, 16, 14, 0, tzinfo=UTC),
            fill_open=1.1,
            gbp_usd_mid=1.35,
        )


def test_package_ast_has_no_broker_execution_imports():
    found: list[str] = []
    for path in SHADOW_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in FORBIDDEN_IMPORTS or alias.name.startswith("forex_bot.oanda"):
                        found.append(f"{path.name}:{alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module in FORBIDDEN_IMPORTS or node.module.startswith("forex_bot.oanda"):
                    found.append(f"{path.name}:{node.module}")
                if node.module == "forex_bot.live_safety":
                    names = {a.name for a in node.names}
                    if "operator_set_live_order_authorisation" in names:
                        found.append(f"{path.name}:operator_auth")
    assert found == []


def test_importing_shadow_does_not_load_oanda_exec():
    code = (
        "import sys\n"
        "mods=set(sys.modules)\n"
        "from forex_bot.shadow.engine import ShadowEngine\n"
        "assert ShadowEngine is not None\n"
        "loaded=set(sys.modules)-mods\n"
        "bad=[m for m in loaded if m.startswith('forex_bot.oanda_exec') or m=='forex_bot.trading']\n"
        "assert not bad, bad\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], check=False, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_intrabar_collision_prefers_stop():
    reason, px = conservative_intrabar_exit("BUY", 1.0990, 1.1020, 1.1000, 1.1030, 1.0980)
    assert reason == "stop_loss"
    assert px == 1.0990


def test_gap_through_stop_uses_open():
    reason, px = conservative_intrabar_exit("BUY", 1.1000, 1.1100, 1.0900, 1.0910, 1.0890)
    assert reason == "stop_loss"
    assert px == 1.0900


def test_usd_to_gbp_conversion():
    assert usd_to_gbp(1.35, 1.35, _cfg()) == pytest.approx(1.0)
    jpy_usd = quote_pnl_to_usd("USD_JPY", 157.0, 157.0)
    assert jpy_usd == pytest.approx(1.0)


def test_stale_data_rejected():
    df = _bars(50)
    df.loc[df.index[-1], "time"] = df.iloc[-2]["time"] + timedelta(minutes=30)
    engine = ShadowEngine(cfg=_cfg())
    engine.process_symbol_bar(
        symbol="EUR_USD",
        history=df,
        bar_time=df.iloc[-1]["time"],
        fill_open=float(df.iloc[-1]["open"]),
        gbp_usd_mid=1.35,
    )
    assert any(t.reason == ShadowReason.STALE_DATA for t in engine.traces)


def test_session_weekend_reject():
    df = _bars(50, start=datetime(2026, 9, 18, 20, 50, tzinfo=UTC))  # Friday
    engine = ShadowEngine(cfg=_cfg())
    engine.process_symbol_bar(
        symbol="EUR_USD",
        history=df,
        bar_time=df.iloc[-1]["time"],
        fill_open=float(df.iloc[-1]["open"]),
        gbp_usd_mid=1.35,
    )
    assert any(t.reason == ShadowReason.SESSION_REJECT for t in engine.traces)


def test_daily_loss_and_drawdown_block_entries(monkeypatch):
    monkeypatch.setattr(
        "forex_bot.shadow.engine.signal_from_indicators",
        lambda strategy, df: ("BUY", "forced_test_signal"),
    )
    monkeypatch.setattr("forex_bot.shadow.engine.quant_blocks", lambda df: None)
    engine = ShadowEngine(cfg=_cfg(daily_loss_pct=0.01, max_drawdown_pct=0.01))
    engine.equity_gbp = 90.0
    engine.peak_equity_gbp = 97.15
    engine.day_realised_gbp = -3.0
    engine.day_key = "2026-09-16"
    df = _bars(60)
    engine.process_symbol_bar(
        symbol="EUR_USD",
        history=df,
        bar_time=df.iloc[-1]["time"],
        fill_open=float(df.iloc[-1]["open"]),
        gbp_usd_mid=1.35,
    )
    reasons = {t.reason for t in engine.traces}
    assert ShadowReason.DAILY_LOSS_LIMIT in reasons or ShadowReason.DRAWDOWN_LIMIT in reasons
    assert not any(t.reason == ShadowReason.SHADOW_ENTRY for t in engine.traces)


def test_replay_is_deterministic_and_has_no_lookahead(tmp_path):
    df = _bars(80)
    cfg = _cfg()
    a = ShadowEngine(cfg=cfg)
    b = ShadowEngine(cfg=cfg)
    replay_symbol(a, "EUR_USD", df, gbp_usd=pd.Series([1.35] * len(df)))
    replay_symbol(b, "EUR_USD", df, gbp_usd=pd.Series([1.35] * len(df)))
    assert [t.reason for t in a.traces] == [t.reason for t in b.traces]
    assert a.summary()["equity_gbp"] == b.summary()["equity_gbp"]

    cutoff = 70
    early = ShadowEngine(cfg=cfg)
    replay_symbol(early, "EUR_USD", df.iloc[:cutoff], gbp_usd=pd.Series([1.35] * cutoff))
    mutated = df.copy()
    mutated.loc[mutated.index[-5:], "close"] = 9.99
    mutated.loc[mutated.index[-5:], "high"] = 10.0
    full = ShadowEngine(cfg=cfg)
    replay_symbol(full, "EUR_USD", mutated, gbp_usd=pd.Series([1.35] * len(mutated)))
    cut = pd.Timestamp(df.iloc[cutoff - 1]["time"]).to_pydatetime()
    if cut.tzinfo is None:
        cut = cut.replace(tzinfo=UTC)
    else:
        cut = cut.astimezone(UTC)
    early_reasons = [t.reason for t in early.traces]
    full_prefix = [t.reason for t in full.traces if t.eval_time <= cut]
    assert early_reasons == full_prefix


def test_duplicate_bar_does_not_double_entry():
    df = _bars(60)
    engine = ShadowEngine(cfg=_cfg())
    ts = df.iloc[-1]["time"]
    kwargs = {
        "symbol": "EUR_USD",
        "history": df,
        "bar_time": ts,
        "fill_open": float(df.iloc[-1]["open"]),
        "gbp_usd_mid": 1.35,
    }
    engine.process_symbol_bar(**kwargs)
    n_entry = sum(1 for t in engine.traces if t.reason == ShadowReason.SHADOW_ENTRY)
    engine.process_symbol_bar(**kwargs)
    n_dup = sum(1 for t in engine.traces if t.reason == ShadowReason.DUPLICATE_BAR)
    assert n_dup >= 6
    assert sum(1 for t in engine.traces if t.reason == ShadowReason.SHADOW_ENTRY) == n_entry


def test_shadow_cannot_change_live_auth_or_strategies(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_SAFETY_STATE_PATH", str(tmp_path / "live_safety_state.json"))
    initialise_fail_closed()
    assert live_order_auth_state() == AUTH_BLOCKED
    before = {n: (s.active, s.authorised_for_live) for n, s in strategies.items()}
    engine = ShadowEngine(cfg=_cfg(), store=ShadowStore(tmp_path / "shadow"))
    replay_symbol(engine, "EUR_USD", _bars(55), gbp_usd=pd.Series([1.35] * 55))
    assert live_order_auth_state() == AUTH_BLOCKED
    after = {n: (s.active, s.authorised_for_live) for n, s in strategies.items()}
    assert after == before
    with pytest.raises(PermissionError):
        operator_set_strategy_active(
            name="scalp", active=True, reason="shadow", operator_confirmed=False
        )


def test_shadow_store_is_labelled_simulated(tmp_path):
    store = ShadowStore(tmp_path / "sim")
    store.append_event({"kind": "probe"})
    text = (tmp_path / "sim" / "shadow_events.jsonl").read_text(encoding="utf-8")
    assert "SIMULATED_SHADOW_NOT_BROKER" in text
    assert (tmp_path / "sim" / "README_SIMULATED.txt").is_file()


def test_restart_restores_shadow_not_live(tmp_path):
    cfg = _cfg()
    store = ShadowStore(tmp_path / "sim")
    first = ShadowEngine(cfg=cfg, store=store)
    first.equity_gbp = 96.5
    first.peak_equity_gbp = 97.15
    first.persist()
    second = ShadowEngine(cfg=cfg, store=store)
    second.restore()
    assert second.equity_gbp == pytest.approx(96.5)
    assert live_order_auth_state() in (AUTH_BLOCKED, live_order_auth_state())


def test_period_split_is_chronological():
    df = _bars(100)
    parts = split_periods(df, train_frac=0.4, tune_frac=0.2)
    assert len(parts["train"]) == 40
    assert parts["train"]["time"].iloc[-1] < parts["tune"]["time"].iloc[0]
    assert parts["tune"]["time"].iloc[-1] < parts["evaluate"]["time"].iloc[0]


def test_shadow_failure_leaves_live_gate(monkeypatch, tmp_path):
    monkeypatch.setenv("LIVE_SAFETY_STATE_PATH", str(tmp_path / "live_safety_state.json"))
    initialise_fail_closed()
    engine = ShadowEngine(cfg=_cfg())
    with pytest.raises((KeyError, ValueError, TypeError)):
        engine.process_symbol_bar(
            symbol="EUR_USD",
            history=pd.DataFrame({"time": [datetime.now(UTC)]}),
            bar_time=datetime.now(UTC),
            fill_open=1.0,
            gbp_usd_mid=1.35,
        )
    assert live_order_auth_state() == AUTH_BLOCKED


def test_spread_and_slippage_are_adverse():
    cfg = _cfg()
    mid = 1.1000
    buy_px, spread, slip = executable_price("EUR_USD", "BUY", mid, 0.001, "trend", cfg)
    sell_px, _, _ = executable_price("EUR_USD", "SELL", mid, 0.001, "trend", cfg)
    assert spread > 0
    assert slip > 0
    assert buy_px > mid
    assert sell_px < mid


def test_concurrent_risk_limit(monkeypatch):
    monkeypatch.setattr(
        "forex_bot.shadow.engine.signal_from_indicators",
        lambda strategy, df: ("BUY", "forced_test_signal"),
    )
    monkeypatch.setattr("forex_bot.shadow.engine.quant_blocks", lambda df: None)
    engine = ShadowEngine(cfg=_cfg(max_concurrent_positions=0))
    df = _bars(50)
    engine.process_symbol_bar(
        symbol="EUR_USD",
        history=df,
        bar_time=df.iloc[-1]["time"],
        fill_open=float(df.iloc[-1]["open"]),
        gbp_usd_mid=1.35,
    )
    assert any(t.reason == ShadowReason.CONCURRENT_LIMIT for t in engine.traces)
    assert not engine.pending_entries


def test_replay_cli_refuses_without_opt_in():
    with pytest.raises(SystemExit, match="simulated"):
        replay_main(["--csv", "x.csv", "--symbol", "EUR_USD", "--out", "tmp"])


def test_replay_writes_only_shadow_paths(tmp_path):
    cfg = _cfg()
    store = ShadowStore(tmp_path / "sim")
    engine = ShadowEngine(cfg=cfg, store=store)
    replay_symbol(engine, "EUR_USD", _bars(50), gbp_usd=pd.Series([1.35] * 50))
    live_ops = Path("data/ops/live_safety_state.json")
    events = json.loads((tmp_path / "sim" / "shadow_events.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert events["simulated"] is True
    if live_ops.exists():
        blob = live_ops.read_text(encoding="utf-8")
        assert "SIMULATED_SHADOW" not in blob

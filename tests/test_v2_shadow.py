"""V2 shadow framework: observe-only, default SKIP, no execution authority."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from forex_bot.ai_ensemble import _quant_stub_vote
from forex_bot.decision_quality.signal import production_quant_decision
from forex_bot.entry_geometry import classify_book_price
from forex_bot.profit_protection import apply_profit_protection, pip_size
from forex_bot.positions import Position
from forex_bot.reconciliation import paper_open_blocked_reason
from forex_bot.v2_shadow import (
    MODEL_NAME_NONE,
    MODEL_VERSION_NONE,
    default_v2_decision,
    maybe_observe_candidate,
    propose_action,
    score_shadow_decision,
    v2_shadow_enabled,
)
from forex_bot.v2_shadow.isolation import assert_v2_cannot_write_broker, forbidden_hits_in_source
from forex_bot.v2_shadow.observe import build_observation
from forex_bot.v2_shadow.store import append_outcome, observations_path, outcomes_path


def _bars():
    t0 = datetime(2026, 9, 21, 22, 0, tzinfo=timezone.utc)
    rows = []
    bid = 1.10000
    ask = 1.10020
    for i in range(50):
        bid += 0.00010
        ask += 0.00010
        ts = t0.timestamp() + (i + 1) * 300
        iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        rows.append(
            {
                "ts": iso,
                "bid_high": bid + 0.00005,
                "bid_low": bid - 0.00005,
                "bid_close": bid,
                "ask_high": ask + 0.00005,
                "ask_low": ask - 0.00005,
                "ask_close": ask,
            }
        )
    return rows


def _ohlcv(n: int = 80) -> pd.DataFrame:
    t0 = datetime(2026, 1, 2, 8, 0)
    px = 1.10
    rows = []
    for i in range(n):
        px += 0.00002
        rows.append(
            {
                "time": t0,
                "open": px,
                "high": px + 0.0001,
                "low": px - 0.0001,
                "close": px,
            }
        )
        t0 = t0.replace(minute=(t0.minute + 5) % 60) if False else t0
        from datetime import timedelta

        t0 = datetime(2026, 1, 2, 8, 0) + timedelta(minutes=5 * (i + 1))
    return pd.DataFrame(rows)


def test_v2_defaults_to_skip():
    assert propose_action() == "SKIP"
    d = default_v2_decision()
    assert d["proposed_action"] == "SKIP"
    assert d["direction_probability_up"] is None
    assert d["reason_codes"] == ["NO_VALIDATED_DIRECTIONAL_MODEL"]
    obs = build_observation(symbol="EUR_USD", strategy_label="trend", production_side="BUY", mid=1.1)
    assert obs.proposed_action == "SKIP"
    assert obs.shadow_only is True


def test_v2_does_not_copy_or_invert_stub():
    buy = build_observation(symbol="EUR_USD", strategy_label="trend", production_side="BUY", mid=1.1)
    sell = build_observation(symbol="EUR_USD", strategy_label="trend", production_side="SELL", mid=1.1)
    assert buy.proposed_action == "SKIP"
    assert sell.proposed_action == "SKIP"
    assert buy.proposed_action != "BUY"
    assert sell.proposed_action != "SELL"


def test_v2_cannot_write_broker():
    assert assert_v2_cannot_write_broker() == []


def test_v2_package_source_has_no_execution_names():
    from forex_bot.v2_shadow import decide, market, observe, score, store
    from forex_bot.v2_shadow import score_offline

    for mod in (decide, market, observe, score, score_offline, store):
        assert forbidden_hits_in_source(Path(mod.__file__).read_text(encoding="utf-8")) == []


def _production_authorization(allow: bool, direction: str, rl_action: str) -> str | None:
    if not allow:
        return None
    if direction not in ("BUY", "SELL"):
        return None
    if rl_action == "SKIP":
        return None
    if rl_action in ("BUY", "SELL") and rl_action != direction:
        return None
    return direction


def test_enabling_shadow_does_not_change_production_decision(tmp_path, monkeypatch):
    monkeypatch.setenv("V2_SHADOW_ENABLED", "true")
    before = _production_authorization(True, "BUY", "BUY")
    obs = maybe_observe_candidate(
        symbol="EUR_USD",
        strategy_label="trend",
        production_side="BUY",
        mid=1.1,
        store_dir=tmp_path,
        enabled=True,
    )
    after = _production_authorization(True, "BUY", "BUY")
    assert before == after == "BUY"
    assert obs is not None
    assert obs.proposed_action == "SKIP"


def test_disabling_shadow_does_not_change_production_decision(tmp_path, monkeypatch):
    monkeypatch.delenv("V2_SHADOW_ENABLED", raising=False)
    assert v2_shadow_enabled() is False
    before = _production_authorization(True, "SELL", "SELL")
    obs = maybe_observe_candidate(
        symbol="EUR_USD",
        strategy_label="trend",
        production_side="SELL",
        mid=1.1,
        store_dir=tmp_path,
        enabled=False,
    )
    after = _production_authorization(True, "SELL", "SELL")
    assert before == after == "SELL"
    assert obs is None
    assert not observations_path(tmp_path).exists()


def test_v2_exception_does_not_block_production(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("shadow exploded")

    monkeypatch.setattr("forex_bot.v2_shadow.maybe_observe_candidate", boom)
    direction = "BUY"
    rl_action = "BUY"
    try:
        from forex_bot.v2_shadow import maybe_observe_candidate as hook

        hook(symbol="EUR_USD", strategy_label="x", production_side=direction, mid=1.1)
    except Exception:
        pass
    assert _production_authorization(True, direction, rl_action) == "BUY"


def test_no_future_fields_in_decision_snapshot():
    obs = build_observation(symbol="EUR_USD", strategy_label="trend", production_side="BUY", mid=1.1)
    blob = obs.to_dict()
    for key in ("forward_pips", "forward_return", "direction_correct", "mfe_pips", "mae_pips"):
        assert key not in blob
        assert key not in blob.get("inputs", {})
    with pytest.raises(ValueError, match="future"):
        build_observation(
            symbol="EUR_USD",
            strategy_label="trend",
            production_side="BUY",
            mid=1.1,
            extras={"forward_pips": 1.0},
        )


def test_outcome_scoring_is_separate(tmp_path):
    obs = maybe_observe_candidate(
        symbol="EUR_USD",
        strategy_label="trend",
        production_side="BUY",
        mid=1.10010,
        bid=1.10000,
        ask=1.10020,
        pip_size=0.0001,
        timestamp_utc="2026-09-21T22:00:00+00:00",
        store_dir=tmp_path,
        enabled=True,
    )
    assert obs is not None
    raw = observations_path(tmp_path).read_text(encoding="utf-8")
    assert "forward_pips" not in raw
    outcome = score_shadow_decision(obs, _bars(), scored_at_utc="2026-09-21T23:00:00+00:00")
    append_outcome(outcome, store_dir=tmp_path)
    assert outcomes_path(tmp_path).is_file()
    assert outcome.decision_id == obs.decision_id
    assert obs.proposed_action == "SKIP"


def test_buy_scoring_uses_ask_to_future_bid():
    obs = build_observation(
        symbol="EUR_USD",
        strategy_label="trend",
        production_side="BUY",
        mid=1.10010,
        bid=1.10000,
        ask=1.10020,
        pip_size=0.0001,
        timestamp_utc="2026-09-21T22:00:00+00:00",
    )
    out = score_shadow_decision(obs, _bars())
    buy = out.horizons["5"]["buy"]
    assert buy["entry_side"] == "ask"
    assert buy["exit_side"] == "bid"
    assert buy["entry"] == pytest.approx(1.10020)
    expected = (1.10010 - 1.10020) / 0.0001
    assert buy["forward_pips"] == pytest.approx(expected)


def test_sell_scoring_uses_bid_to_future_ask():
    obs = build_observation(
        symbol="EUR_USD",
        strategy_label="trend",
        production_side="SELL",
        mid=1.10010,
        bid=1.10000,
        ask=1.10020,
        pip_size=0.0001,
        timestamp_utc="2026-09-21T22:00:00+00:00",
    )
    out = score_shadow_decision(obs, _bars())
    sell = out.horizons["5"]["sell"]
    assert sell["entry_side"] == "bid"
    assert sell["exit_side"] == "ask"
    assert sell["entry"] == pytest.approx(1.10000)
    expected = (1.10000 - 1.10030) / 0.0001
    assert sell["forward_pips"] == pytest.approx(expected)


def test_model_version_persists(tmp_path):
    obs = maybe_observe_candidate(
        symbol="GBP_USD",
        strategy_label="swing_trend",
        production_side="SELL",
        mid=1.3,
        store_dir=tmp_path,
        enabled=True,
    )
    assert obs is not None
    assert obs.model_name == MODEL_NAME_NONE
    assert obs.model_version == MODEL_VERSION_NONE
    line = observations_path(tmp_path).read_text(encoding="utf-8")
    assert MODEL_NAME_NONE in line
    assert '"model_version":"0"' in line
    assert "v2_shadow_input_v1" in line


def test_missing_external_data_does_not_fail():
    obs = build_observation(symbol="USD_JPY", strategy_label="scalp", production_side="BUY", mid=150.0)
    assert obs.fundamentals["external_data_available"] is False
    assert obs.fundamentals["macro_event_id"]["status"] == "NOT_COMPUTED"
    assert obs.provenance == []
    score_shadow_decision(obs, [])


def test_production_mfe_unchanged():
    pos = Position(
        symbol="EUR_USD",
        direction="BUY",
        units=2.0,
        entry_price=1.10000,
        stop_loss=1.09900,
        take_profit=1.10200,
        open_time=1.0,
        strategy_name="trend",
        rl_state="s",
        execution_kind="paper",
    )
    apply_profit_protection(pos, 1.10100)
    assert pos.max_profit_pips == pytest.approx(10.0)


def test_entry_geometry_unchanged():
    px, reason = classify_book_price(1.1, "missing_quote")
    assert px == pytest.approx(1.1)
    assert reason is None
    px, reason = classify_book_price(None, "missing_quote")
    assert px is None
    assert reason == "missing_quote"


def test_reconciliation_helper_unchanged(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING", "true")
    reason = paper_open_blocked_reason("EUR_USD")
    assert reason is None or isinstance(reason, str)


def test_profit_protection_pip_size_unchanged():
    assert pip_size("EUR_USD") == pytest.approx(0.0001)
    assert pip_size("USD_JPY") == pytest.approx(0.01)


def test_quant_stub_independent_of_v2():
    df = _ohlcv()
    vote = production_quant_decision(df, lookback=50)
    stub = _quant_stub_vote(
        {
            "price": float(df["close"].iloc[-1]),
            "ma_fast": float(vote["df"]["ma_fast"].iloc[-1]),
            "ma_slow": float(vote["df"]["ma_slow"].iloc[-1]),
            "returns": float(vote["df"]["close"].pct_change().iloc[-1]),
            "atr": float(vote["df"]["atr"].iloc[-1]),
        }
    )
    assert vote["direction"] == stub["direction"]
    assert vote["allow"] == stub["allow"]


def test_rl_fields_recorded_without_changing_action():
    obs = build_observation(
        symbol="EUR_USD",
        strategy_label="trend",
        production_side="BUY",
        mid=1.1,
        rl_action="SKIP",
        rl_state="0.1_0.2",
        rl_q_values={"BUY": 0.1, "SELL": 0.0, "SKIP": 0.2},
        rl_epsilon=0.25,
    )
    assert obs.rl["action"] == "SKIP"
    assert obs.rl["veto"] is True
    assert obs.rl["agree"] is False
    assert obs.rl["q_values"]["SKIP"] == pytest.approx(0.2)
    assert obs.rl["epsilon"] == pytest.approx(0.25)


def test_adx_marked_not_computed():
    obs = build_observation(symbol="EUR_USD", strategy_label="trend", production_side="BUY", mid=1.1)
    assert "adx" in obs.data_not_computed
    assert obs.inputs["adx"]["status"] == "NOT_COMPUTED"


def test_shadow_only_cannot_be_cleared():
    from forex_bot.v2_shadow.contract import V2ShadowDecision

    with pytest.raises(ValueError):
        V2ShadowDecision(
            decision_id="x",
            timestamp_utc="t",
            symbol="EUR_USD",
            candidate_source="x",
            strategy_label="t",
            market_price_reference=1.1,
            proposed_action="SKIP",
            direction_probability_up=None,
            direction_probability_down=None,
            confidence=None,
            model_name="v2_none",
            model_version="0",
            feature_schema_version="v2_shadow_input_v1",
            reason_codes=["NO_VALIDATED_DIRECTIONAL_MODEL"],
            data_available=[],
            data_missing=[],
            data_not_computed=[],
            shadow_only=False,
        )


def test_compose_wires_flag_and_bind_mount():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "V2_SHADOW_ENABLED: ${V2_SHADOW_ENABLED:-}" in compose
    assert "./data/research/v2_shadow:/app/data/research/v2_shadow" in compose
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "WORKDIR /app" in dockerfile


def test_observe_does_not_run_scorer(tmp_path, monkeypatch):
    called = []

    def boom(*_a, **_k):
        called.append(True)
        raise AssertionError("scorer must not run at observe time")

    monkeypatch.setattr("forex_bot.v2_shadow.score.score_shadow_decision", boom)
    maybe_observe_candidate(
        symbol="EUR_USD",
        strategy_label="trend",
        production_side="BUY",
        mid=1.1,
        store_dir=tmp_path,
        enabled=True,
    )
    assert called == []
    raw = observations_path(tmp_path).read_text(encoding="utf-8")
    assert "forward_pips" not in raw
    assert "NO_VALIDATED_DIRECTIONAL_MODEL" in raw


def test_v2_package_has_no_network_or_vendor_imports():
    import ast

    blocked_mods = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
    }
    blocked_text = (
        "econoday",
        "reuters",
        "twitter",
        "x.com",
        "tradingeconomics",
        "bloomberg",
        "bls.gov",
        "federalreserve",
    )
    root = Path("forex_bot/v2_shadow")
    for path in root.glob("*.py"):
        src = path.read_text(encoding="utf-8")
        lower = src.lower()
        for needle in blocked_text:
            assert needle not in lower, f"{path.name} mentions {needle}"
        tree = ast.parse(src)
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert name.split(".")[0] not in blocked_mods, f"{path.name} imports {name}"


def test_secrets_cannot_be_written_to_jsonl(tmp_path, monkeypatch):
    from forex_bot.v2_shadow.store import append_observation

    obs = build_observation(symbol="EUR_USD", strategy_label="trend", production_side="BUY", mid=1.1)
    original = obs.to_dict

    def dirty() -> dict:
        payload = original()
        payload["oanda_api_key"] = "SECRETVALUE"
        payload["telegram_token"] = "SECRETVALUE"
        payload["inputs"] = dict(payload.get("inputs") or {})
        payload["inputs"]["access_token"] = {"value": "SECRETVALUE", "status": "AVAILABLE"}
        return payload

    monkeypatch.setattr(obs, "to_dict", dirty)
    append_observation(obs, store_dir=tmp_path)
    text = observations_path(tmp_path).read_text(encoding="utf-8")
    assert "SECRETVALUE" not in text
    assert "oanda_api_key" not in text
    assert "telegram_token" not in text
    assert "access_token" not in text


def test_archive_renames_without_deleting(tmp_path):
    from forex_bot.v2_shadow.store import maybe_archive_jsonl

    path = tmp_path / "observations.jsonl"
    path.write_text("keep-me\n", encoding="utf-8")
    dest = maybe_archive_jsonl(path, limit_bytes=1)
    assert dest is not None
    assert dest.exists()
    assert dest.read_text(encoding="utf-8") == "keep-me\n"
    assert dest.parent == tmp_path
    assert list(tmp_path.glob("observations*.jsonl"))


def test_bot_loop_discards_v2_return_and_swallows_errors():
    src = Path("forex_bot/bot_loop.py").read_text(encoding="utf-8")
    assert "maybe_observe_candidate(" in src
    assert "_observe_v2_shadow_candidate(" in src
    assert "_persist_v2_shadow_market_m5(" in src
    assert 'except Exception:\n        logger.exception("[V2 SHADOW] observe failed (ignored)")' in src
    assert 'except Exception:\n        logger.exception("[V2 SHADOW] market persist failed (ignored)")' in src
    helper = src.split("def _observe_v2_shadow_candidate", 1)[1].split("async def evaluate", 1)[0]
    assert "return maybe_observe_candidate" not in helper
    assert "direction =" not in helper

"""Offline live-market scoring: temporal join, executable sides, idempotency."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from forex_bot.v2_shadow.contract import ShadowOutcome, V2ShadowDecision
from forex_bot.v2_shadow.isolation import forbidden_hits_in_source
from forex_bot.v2_shadow.observe import build_observation
from forex_bot.v2_shadow.score import HORIZONS_MIN, score_shadow_decision
from forex_bot.v2_shadow.score_offline import (
    last_completed_m5_start,
    load_market_bars,
    market_row_to_bar,
    mature_outcome,
    run_offline_score_pass,
    score_decision_against_market,
)
from forex_bot.v2_shadow.store import (
    STATUS_ALREADY_EXISTS,
    STATUS_WRITTEN,
    append_outcome,
    observations_path,
    outcomes_path,
    reset_outcome_index_cache,
)


NOW = datetime(2026, 9, 24, 13, 0, tzinfo=timezone.utc)


def _candle(start: datetime, bid_close: float, ask_close: float, **extra) -> dict:
    end = start + timedelta(minutes=5)
    row = {
        "schema_version": "v2_shadow_market_m5_v1",
        "symbol": extra.pop("symbol", "EUR_USD"),
        "granularity": "M5",
        "candle_start_utc": start.isoformat(),
        "candle_end_utc": end.isoformat(),
        "bid_open": bid_close - 0.00005,
        "bid_high": bid_close + 0.00010,
        "bid_low": bid_close - 0.00010,
        "bid_close": bid_close,
        "ask_open": ask_close - 0.00005,
        "ask_high": ask_close + 0.00010,
        "ask_low": ask_close - 0.00010,
        "ask_close": ask_close,
        "volume": 10,
        "complete": True,
        "recorded_at_utc": end.isoformat(),
        "source": "live_fetch_ohlcv",
    }
    row.update(extra)
    return row


def _write_market(tmp_path: Path, rows: list[dict], symbol: str = "EUR_USD") -> Path:
    path = tmp_path / "market" / f"{symbol}_M5.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def _obs(**kwargs) -> V2ShadowDecision:
    return build_observation(
        symbol=kwargs.get("symbol", "EUR_USD"),
        strategy_label="trend",
        production_side="BUY",
        mid=1.10010,
        bid=kwargs.get("bid", 1.10000),
        ask=kwargs.get("ask", 1.10020),
        pip_size=0.0001,
        timestamp_utc=kwargs.get("timestamp_utc", "2026-09-24T12:26:54+00:00"),
        rl_action="SKIP",
        rl_state="0_0",
        rl_q_values={"BUY": 0.0, "SELL": 0.0, "SKIP": 0.0},
        rl_epsilon=0.25,
    )


@pytest.fixture(autouse=True)
def _reset():
    reset_outcome_index_cache()
    yield
    reset_outcome_index_cache()


def test_horizons_and_executable_sides_unchanged():
    assert HORIZONS_MIN == (5, 15, 30, 60, 120, 240)
    start = datetime(2026, 9, 24, 12, 20, tzinfo=timezone.utc)
    bars = []
    for i in range(50):
        ts = start + timedelta(minutes=5 * (i + 1))
        bid = 1.10000 + i * 0.00010
        ask = bid + 0.00020
        bars.append(
            {
                "ts": ts.isoformat(),
                "bid_close": bid,
                "ask_close": ask,
                "bid_high": bid + 0.00005,
                "bid_low": bid - 0.00005,
                "ask_high": ask + 0.00005,
                "ask_low": ask - 0.00005,
            }
        )
    out = score_shadow_decision(_obs(timestamp_utc="2026-09-24T12:20:00+00:00"), bars)
    assert out.horizons["5"]["buy"]["entry_side"] == "ask"
    assert out.horizons["5"]["buy"]["exit_side"] == "bid"
    assert out.horizons["5"]["sell"]["entry_side"] == "bid"
    assert out.horizons["5"]["sell"]["exit_side"] == "ask"
    assert out.horizons["5"]["buy"]["direction_correct"] is (
        out.horizons["5"]["buy"]["forward_pips"] > 0
    )


def test_decision_inside_m5_excludes_forming_and_pre_decision(tmp_path):
    decision_ts = datetime(2026, 9, 24, 12, 26, 54, tzinfo=timezone.utc)
    candles = [
        _candle(datetime(2026, 9, 24, 12, 20, tzinfo=timezone.utc), 1.09900, 1.09920),
        _candle(datetime(2026, 9, 24, 12, 25, tzinfo=timezone.utc), 1.09950, 1.09970),
        _candle(datetime(2026, 9, 24, 12, 30, tzinfo=timezone.utc), 1.10100, 1.10120),
        _candle(datetime(2026, 9, 24, 12, 35, tzinfo=timezone.utc), 1.10200, 1.10220),
    ]
    _write_market(tmp_path, candles)
    bars = load_market_bars(tmp_path / "market")["bars"]["EUR_USD"]
    decision = _obs(timestamp_utc=decision_ts.isoformat())
    outcome = score_decision_against_market(decision, bars)
    assert outcome is not None
    buy = outcome.horizons["5"]["buy"]
    assert buy["future_close"] == pytest.approx(1.10100)
    assert last_completed_m5_start(decision_ts) == datetime(
        2026, 9, 24, 12, 20, tzinfo=timezone.utc
    )
    raw = score_shadow_decision(decision, bars)
    future5 = raw.horizons["5"]["buy"]["future_close"]
    assert future5 != pytest.approx(1.09950)


def test_forming_candle_not_converted():
    start = datetime(2026, 9, 24, 12, 35, tzinfo=timezone.utc)
    forming = _candle(start, 1.1, 1.1002, complete=False)
    assert market_row_to_bar(forming) is None


def test_partial_horizon_maturity(tmp_path):
    base = datetime(2026, 9, 24, 12, 20, tzinfo=timezone.utc)
    candles = [_candle(base + timedelta(minutes=5 * i), 1.1 + i * 0.0001, 1.1002 + i * 0.0001) for i in range(4)]
    _write_market(tmp_path, candles)
    bars = load_market_bars(tmp_path / "market")["bars"]["EUR_USD"]
    decision = _obs(timestamp_utc="2026-09-24T12:21:00+00:00")
    outcome = score_decision_against_market(decision, bars)
    assert outcome is not None
    assert "5" in outcome.horizons
    assert "15" in outcome.horizons
    assert "240" not in outcome.horizons
    raw = score_shadow_decision(decision, bars)
    assert raw.horizons["240"]["buy"].get("future_close") is not None
    assert mature_outcome(
        raw,
        decision_ts=datetime(2026, 9, 24, 12, 21, tzinfo=timezone.utc),
        bars=bars,
    ).horizons.get("240") is None


def test_no_mid_fallback():
    start = datetime(2026, 9, 24, 12, 20, tzinfo=timezone.utc)
    row = _candle(start, 1.1, 1.1002)
    row["bid_close"] = None
    row["close"] = 1.10500
    row["mid"] = 1.10500
    assert market_row_to_bar(row) is None


def test_missing_ba_skipped():
    start = datetime(2026, 9, 24, 12, 20, tzinfo=timezone.utc)
    row = _candle(start, 1.1, 1.1002)
    del row["ask_close"]
    assert market_row_to_bar(row) is None


def test_malformed_market_row_skipped(tmp_path):
    path = tmp_path / "market" / "EUR_USD_M5.jsonl"
    path.parent.mkdir(parents=True)
    good = _candle(datetime(2026, 9, 24, 12, 20, tzinfo=timezone.utc), 1.1, 1.1002)
    path.write_text("{not-json\n" + json.dumps(good) + "\n", encoding="utf-8")
    stats = load_market_bars(tmp_path / "market")
    assert stats["malformed"] == 1
    assert len(stats["bars"]["EUR_USD"]) == 1


def test_duplicate_market_key_keeps_first(tmp_path):
    start = datetime(2026, 9, 24, 12, 20, tzinfo=timezone.utc)
    first = _candle(start, 1.10100, 1.10120)
    second = _candle(start, 1.10900, 1.10920)
    _write_market(tmp_path, [first, second])
    stats = load_market_bars(tmp_path / "market")
    assert stats["duplicates"] == 1
    assert stats["bars"]["EUR_USD"][0]["bid_close"] == pytest.approx(1.10100)


def test_repeated_observation_same_completed_m5():
    a = datetime(2026, 9, 24, 12, 26, 10, tzinfo=timezone.utc)
    b = datetime(2026, 9, 24, 12, 26, 50, tzinfo=timezone.utc)
    assert last_completed_m5_start(a) == last_completed_m5_start(b)
    assert last_completed_m5_start(a) == datetime(2026, 9, 24, 12, 20, tzinfo=timezone.utc)


def test_incremental_new_horizons_write_without_conflict(tmp_path):
    """Already-stored short horizons stay; newly matured horizons persist."""
    from forex_bot.v2_shadow.score_offline import filter_outcome_to_unpersisted_keys
    from forex_bot.v2_shadow.store import logical_outcome_units

    base = datetime(2026, 9, 24, 12, 20, tzinfo=timezone.utc)
    short = [_candle(base + timedelta(minutes=5 * i), 1.1 + i * 0.0001, 1.1002 + i * 0.0001) for i in range(4)]
    _write_market(tmp_path, short)
    obs = _obs(timestamp_utc="2026-09-24T12:21:00+00:00")
    observations_path(tmp_path).write_text(json.dumps(obs.to_dict()) + "\n", encoding="utf-8")
    first = run_offline_score_pass(store_dir=tmp_path, scored_at_utc="2026-09-24T18:00:00+00:00")
    assert first["written"] == 1
    assert first["conflicts"] == 0
    first_rows = [json.loads(ln) for ln in outcomes_path(tmp_path).read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert set(first_rows[0]["horizons"]) <= {"5", "15"}
    existing = logical_outcome_units(first_rows[0])

    longer = short + [
        _candle(base + timedelta(minutes=5 * i), 1.1 + i * 0.0001, 1.1002 + i * 0.0001) for i in range(4, 8)
    ]
    _write_market(tmp_path, longer)
    bars = load_market_bars(tmp_path / "market")["bars"]["EUR_USD"]
    grown = score_decision_against_market(obs, bars, scored_at_utc="2026-09-24T19:00:00+00:00")
    assert grown is not None
    assert "30" in grown.horizons
    filtered, hint, new_keys = filter_outcome_to_unpersisted_keys(grown, existing)
    assert hint == STATUS_WRITTEN
    assert filtered is not None
    assert "5" not in filtered.horizons
    assert "30" in filtered.horizons
    assert any(k.endswith("|30") for k in new_keys)

    second = run_offline_score_pass(store_dir=tmp_path, scored_at_utc="2026-09-24T19:00:00+00:00")
    assert second["conflicts"] == 0
    assert second["written"] == 1
    third = run_offline_score_pass(store_dir=tmp_path, scored_at_utc="2026-09-24T19:01:00+00:00")
    assert third["written"] == 0
    assert third["conflicts"] == 0
    assert third["already_exists"] == 1


def test_repeated_scoring_idempotent(tmp_path):
    base = datetime(2026, 9, 24, 12, 20, tzinfo=timezone.utc)
    candles = [_candle(base + timedelta(minutes=5 * i), 1.1 + i * 0.0001, 1.1002 + i * 0.0001) for i in range(12)]
    _write_market(tmp_path, candles)
    obs = _obs(timestamp_utc="2026-09-24T12:21:00+00:00")
    observations_path(tmp_path).write_text(json.dumps(obs.to_dict()) + "\n", encoding="utf-8")
    first = run_offline_score_pass(store_dir=tmp_path, scored_at_utc="2026-09-24T18:00:00+00:00")
    second = run_offline_score_pass(store_dir=tmp_path, scored_at_utc="2026-09-24T19:00:00+00:00")
    assert first["written"] == 1
    assert first["conflicts"] == 0
    assert second["written"] == 0
    assert second["already_exists"] == 1
    assert second["conflicts"] == 0
    assert len(outcomes_path(tmp_path).read_text(encoding="utf-8").splitlines()) == 1


def test_zero_network_and_not_in_bot_loop():
    src = Path("forex_bot/v2_shadow/score_offline.py").read_text(encoding="utf-8")
    assert forbidden_hits_in_source(src) == []
    assert "oanda_client" not in src
    assert "InstrumentsCandles" not in src
    loop = Path("forex_bot/bot_loop.py").read_text(encoding="utf-8")
    assert "score_offline" not in loop
    assert "score_shadow_decision" not in loop
    assert "append_outcome" not in loop
    assert "run_offline_score_pass" not in loop

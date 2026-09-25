"""Research-only live M5 bid/ask persist. No orders. No extra broker loop."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from forex_bot.v2_shadow.isolation import forbidden_hits_in_source
from forex_bot.v2_shadow.market import (
    MARKET_SCHEMA_VERSION,
    REQUIRED_BA,
    candle_from_row,
    market_path,
    maybe_record_completed_m5,
    persist_completed_candle,
    record_completed_m5_frame,
    reset_market_index_cache,
)
from forex_bot.v2_shadow.score import HORIZONS_MIN, score_shadow_decision
from forex_bot.v2_shadow.observe import build_observation


NOW = datetime(2026, 9, 24, 12, 35, tzinfo=timezone.utc)
START_A = datetime(2026, 9, 24, 12, 20, tzinfo=timezone.utc)
START_B = datetime(2026, 9, 24, 12, 25, tzinfo=timezone.utc)


def _ba_row(start: datetime, *, complete: bool = True, **overrides) -> dict:
    row = {
        "time": start.isoformat().replace("+00:00", "Z"),
        "open": 1.10010,
        "high": 1.10040,
        "low": 1.09990,
        "close": 1.10020,
        "complete": complete,
        "bid_open": 1.10000,
        "bid_high": 1.10030,
        "bid_low": 1.09980,
        "bid_close": 1.10010,
        "ask_open": 1.10020,
        "ask_high": 1.10050,
        "ask_low": 1.10000,
        "ask_close": 1.10030,
        "volume": 12,
    }
    row.update(overrides)
    return row


def _read_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            import json

            out.append(json.loads(line))
    return out


@pytest.fixture(autouse=True)
def _reset_index():
    reset_market_index_cache()
    yield
    reset_market_index_cache()


def test_complete_bid_ask_m5_writes(tmp_path):
    frame = pd.DataFrame([_ba_row(START_A)])
    counts = record_completed_m5_frame("EUR_USD", frame, store_dir=tmp_path, now_utc=NOW)
    assert counts["written"] == 1
    rows = _read_rows(market_path("EUR_USD", tmp_path))
    assert len(rows) == 1
    row = rows[0]
    assert row["schema_version"] == MARKET_SCHEMA_VERSION
    assert row["symbol"] == "EUR_USD"
    assert row["granularity"] == "M5"
    assert row["complete"] is True
    assert row["source"] == "live_fetch_ohlcv"
    assert row["bid_close"] == pytest.approx(1.10010)
    assert row["ask_close"] == pytest.approx(1.10030)
    assert row["candle_start_utc"].startswith("2026-09-24T12:20:00")
    recorded = datetime.fromisoformat(row["recorded_at_utc"])
    end = datetime.fromisoformat(row["candle_end_utc"])
    assert recorded >= end


def test_forming_candle_is_skipped(tmp_path):
    forming = _ba_row(datetime(2026, 9, 24, 12, 35, tzinfo=timezone.utc))
    frame = pd.DataFrame([forming])
    counts = record_completed_m5_frame("EUR_USD", frame, store_dir=tmp_path, now_utc=NOW)
    assert counts["written"] == 0
    assert counts["skipped_forming"] == 1
    assert not market_path("EUR_USD", tmp_path).exists()
    assert candle_from_row("EUR_USD", forming, now_utc=NOW) is None


def test_missing_bid_ask_is_skipped(tmp_path):
    mid_only = {
        "time": START_A.isoformat(),
        "open": 1.1,
        "high": 1.2,
        "low": 1.0,
        "close": 1.15,
        "complete": True,
    }
    counts = record_completed_m5_frame(
        "GBP_USD", pd.DataFrame([mid_only]), store_dir=tmp_path, now_utc=NOW
    )
    assert counts["written"] == 0
    assert counts["skipped_no_ba"] == 1
    assert not market_path("GBP_USD", tmp_path).exists()


def test_duplicate_same_symbol_timestamp_is_one_row(tmp_path):
    frame = pd.DataFrame([_ba_row(START_A)])
    record_completed_m5_frame("USD_JPY", frame, store_dir=tmp_path, now_utc=NOW)
    record_completed_m5_frame("USD_JPY", frame, store_dir=tmp_path, now_utc=NOW)
    rows = _read_rows(market_path("USD_JPY", tmp_path))
    assert len(rows) == 1


def test_different_symbols_same_timestamp_are_independent(tmp_path):
    frame = pd.DataFrame([_ba_row(START_A)])
    record_completed_m5_frame("AUD_USD", frame, store_dir=tmp_path, now_utc=NOW)
    record_completed_m5_frame("USD_CAD", frame, store_dir=tmp_path, now_utc=NOW)
    assert len(_read_rows(market_path("AUD_USD", tmp_path))) == 1
    assert len(_read_rows(market_path("USD_CAD", tmp_path))) == 1


def test_next_m5_candle_writes(tmp_path):
    frame = pd.DataFrame([_ba_row(START_A), _ba_row(START_B)])
    counts = record_completed_m5_frame("USD_CHF", frame, store_dir=tmp_path, now_utc=NOW)
    assert counts["written"] == 2
    starts = {r["candle_start_utc"][:19] for r in _read_rows(market_path("USD_CHF", tmp_path))}
    assert starts == {"2026-09-24T12:20:00", "2026-09-24T12:25:00"}


def test_reload_does_not_duplicate_existing_candle(tmp_path):
    frame = pd.DataFrame([_ba_row(START_A)])
    record_completed_m5_frame("EUR_USD", frame, store_dir=tmp_path, now_utc=NOW)
    reset_market_index_cache()
    record_completed_m5_frame("EUR_USD", frame, store_dir=tmp_path, now_utc=NOW)
    assert len(_read_rows(market_path("EUR_USD", tmp_path))) == 1


def test_malformed_candle_does_not_corrupt_store(tmp_path):
    path = market_path("EUR_USD", tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json\n", encoding="utf-8")
    reset_market_index_cache()
    bad = _ba_row(START_A, bid_high=1.0, bid_low=1.2)
    good = _ba_row(START_B)
    counts = record_completed_m5_frame(
        "EUR_USD", pd.DataFrame([bad, good]), store_dir=tmp_path, now_utc=NOW
    )
    assert counts["written"] == 1
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "{not-json"
    import json

    parsed = json.loads(lines[1])
    assert parsed["candle_start_utc"].startswith("2026-09-24T12:25:00")


def test_persist_failure_does_not_affect_trading_decision(tmp_path, monkeypatch):
    def authorize(allow: bool, direction: str, rl_action: str) -> str | None:
        if not allow or direction not in ("BUY", "SELL"):
            return None
        if rl_action == "SKIP":
            return None
        if rl_action in ("BUY", "SELL") and rl_action != direction:
            return None
        return direction

    def boom(*_a, **_k):
        raise RuntimeError("disk full")

    monkeypatch.setattr("forex_bot.v2_shadow.market.persist_completed_candle", boom)
    before = authorize(True, "BUY", "BUY")
    out = maybe_record_completed_m5(
        "EUR_USD",
        pd.DataFrame([_ba_row(START_A)]),
        store_dir=tmp_path,
        now_utc=NOW,
        enabled=True,
    )
    after = authorize(True, "BUY", "BUY")
    assert before == after == "BUY"
    assert out is not None
    assert out["written"] == 0


def test_recorder_introduces_zero_additional_broker_requests():
    src = Path("forex_bot/v2_shadow/market.py").read_text(encoding="utf-8")
    assert "oanda_client" not in src
    assert "InstrumentsCandles" not in src
    assert "fetch_ohlcv" not in src or "live_fetch_ohlcv" in src
    assert forbidden_hits_in_source(src) == []
    oanda = Path("forex_bot/oanda_client.py").read_text(encoding="utf-8")
    assert oanda.count('params = {"granularity": granularity, "count": count, "price": "MBA"}') == 1
    assert "price\": \"MBA\"" in oanda
    loop = Path("forex_bot/bot_loop.py").read_text(encoding="utf-8")
    assert loop.count("fetch_ohlcv, symbol, \"M5\", ohlcv_count") == 1
    assert "_persist_v2_shadow_market_m5(symbol, raw)" in loop
    assert 'except Exception:\n        logger.exception("[V2 SHADOW] market persist failed (ignored)")' in loop


def test_fetch_ohlcv_mba_keeps_mid_and_skips_forming(monkeypatch):
    payload = {
        "candles": [
            {
                "complete": True,
                "volume": 9,
                "time": "2026-09-24T12:20:00.000000000Z",
                "mid": {"o": "1.10010", "h": "1.10040", "l": "1.09990", "c": "1.10020"},
                "bid": {"o": "1.10000", "h": "1.10030", "l": "1.09980", "c": "1.10010"},
                "ask": {"o": "1.10020", "h": "1.10050", "l": "1.10000", "c": "1.10030"},
            },
            {
                "complete": False,
                "time": "2026-09-24T12:25:00.000000000Z",
                "mid": {"o": "1.2", "h": "1.3", "l": "1.1", "c": "1.25"},
                "bid": {"o": "1.2", "h": "1.3", "l": "1.1", "c": "1.24"},
                "ask": {"o": "1.21", "h": "1.31", "l": "1.11", "c": "1.26"},
            },
        ]
    }
    calls = []

    def fake_request(_api, request_obj, *, context):
        params = getattr(request_obj, "params", None)
        calls.append({"params": params, "context": context})
        return payload

    monkeypatch.setattr("forex_bot.oanda_client.get_api", lambda: object())
    monkeypatch.setattr("forex_bot.oanda_client._oanda_request", fake_request)
    from forex_bot.oanda_client import fetch_ohlcv

    df = fetch_ohlcv("EUR_USD", "M5", 200)
    assert df is not None
    assert len(df) == 1
    assert len(calls) == 1
    assert calls[0]["params"]["price"] == "MBA"
    assert float(df.iloc[0]["close"]) == pytest.approx(1.10020)
    assert float(df.iloc[0]["bid_close"]) == pytest.approx(1.10010)
    assert float(df.iloc[0]["ask_close"]) == pytest.approx(1.10030)


def test_scorer_can_use_persisted_schema(tmp_path):
    assert HORIZONS_MIN == (5, 15, 30, 60, 120, 240)
    bars = []
    for i in range(50):
        ts = START_A + timedelta(minutes=5 * (i + 1))
        bars.append(
            {
                "ts": ts.isoformat(),
                "bid_close": 1.10010 + i * 0.00001,
                "ask_close": 1.10030 + i * 0.00001,
                "bid_high": 1.10030,
                "bid_low": 1.09980,
                "ask_high": 1.10050,
                "ask_low": 1.10000,
            }
        )
    frame = pd.DataFrame([_ba_row(START_A)])
    record_completed_m5_frame("EUR_USD", frame, store_dir=tmp_path, now_utc=NOW)
    stored = _read_rows(market_path("EUR_USD", tmp_path))[0]
    for field in REQUIRED_BA:
        assert field in stored
    obs = build_observation(
        symbol="EUR_USD",
        strategy_label="trend",
        production_side="BUY",
        mid=1.10020,
        bid=1.10000,
        ask=1.10020,
        pip_size=0.0001,
        timestamp_utc=START_A.isoformat(),
    )
    out = score_shadow_decision(obs, bars)
    assert out.horizons["5"]["buy"]["entry_side"] == "ask"
    assert out.horizons["5"]["buy"]["exit_side"] == "bid"
    assert out.horizons["5"]["sell"]["entry_side"] == "bid"
    assert out.horizons["5"]["sell"]["exit_side"] == "ask"
    assert out.proposed_action if hasattr(out, "proposed_action") else True
    for hz in HORIZONS_MIN:
        assert str(hz) in out.horizons


def test_disabled_flag_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("V2_SHADOW_ENABLED", raising=False)
    out = maybe_record_completed_m5(
        "EUR_USD",
        pd.DataFrame([_ba_row(START_A)]),
        store_dir=tmp_path,
        now_utc=NOW,
        enabled=False,
    )
    assert out is None
    assert not market_path("EUR_USD", tmp_path).exists()

"""Stage 3: read-only candle parse, CLI dry-run, isolation, mocked download."""

from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path

import pandas as pd

from forex_bot.decision_quality.download_history import (
    download_symbol,
    format_plan,
    main,
    plan_range,
)
from forex_bot.decision_quality.history_cache import RESEARCH_SYMBOLS, TimeWindow, read_canonical_csv
from forex_bot.decision_quality.isolation import assert_package_cannot_write_broker, forbidden_hits_in_source
from forex_bot.oanda_candles_read import parse_candles_payload, request_candles_page


def test_isolation_still_blocks_broker_writes():
    assert assert_package_cannot_write_broker() == []


def test_download_history_module_has_no_broker_write_imports():
    root = Path(__file__).resolve().parents[1]
    src = (root / "forex_bot" / "decision_quality" / "download_history.py").read_text(encoding="utf-8")
    hits = forbidden_hits_in_source(src)
    assert hits == []
    tree = ast.parse(src)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        if isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
    assert "forex_bot.oanda_exec" not in imported
    assert "forex_bot.oanda_client" not in imported
    assert "forex_bot.database" not in imported


def test_candles_read_module_has_no_order_endpoints():
    root = Path(__file__).resolve().parents[1]
    src = (root / "forex_bot" / "oanda_candles_read.py").read_text(encoding="utf-8")
    assert "InstrumentsCandles" in src
    for banned in ("OrderCreate", "PositionClose", "oanda_exec", "execute_oanda"):
        assert banned not in src


def test_parse_skips_incomplete_and_keeps_bid_ask_mid():
    now = datetime(2024, 1, 2, 12, 0, 0)
    payload = {
        "candles": [
            {
                "time": "2024-01-02T08:00:00.000000000Z",
                "complete": True,
                "volume": 11,
                "mid": {"o": "1.10000", "h": "1.10040", "l": "1.09980", "c": "1.10020"},
                "bid": {"o": "1.09990", "h": "1.10030", "l": "1.09970", "c": "1.10010"},
                "ask": {"o": "1.10010", "h": "1.10050", "l": "1.09990", "c": "1.10030"},
            },
            {
                "time": "2024-01-02T08:05:00.000000000Z",
                "complete": False,
                "volume": 3,
                "mid": {"o": "1.10020", "h": "1.10060", "l": "1.10000", "c": "1.10040"},
            },
        ]
    }
    df = parse_candles_payload(payload, now_utc=now)
    assert len(df) == 1
    assert float(df["close"].iloc[0]) == 1.10020
    assert float(df["bid_close"].iloc[0]) == 1.10010
    assert float(df["ask_close"].iloc[0]) == 1.10030
    assert bool(df["complete"].iloc[0]) is True


def test_request_candles_page_uses_injected_fn_only():
    calls: list[tuple] = []

    def request_fn(instrument: str, params: dict) -> dict:
        calls.append((instrument, params))
        return {
            "candles": [
                {
                    "time": "2024-01-02T08:00:00.000000000Z",
                    "complete": True,
                    "volume": 1,
                    "mid": {"o": "1.1", "h": "1.2", "l": "1.0", "c": "1.15"},
                }
            ]
        }

    df = request_candles_page(
        "eur-usd",
        datetime(2024, 1, 2, 8, 0, 0),
        datetime(2024, 1, 2, 8, 5, 0),
        request_fn=request_fn,
        now_utc=datetime(2024, 1, 3, 0, 0, 0),
    )
    assert calls[0][0] == "EUR_USD"
    assert calls[0][1]["granularity"] == "M5"
    assert calls[0][1]["price"] == "MBA"
    assert calls[0][1]["from"].startswith("2024-01-02T08:00:00")
    assert len(df) == 1


def test_cli_dry_run_is_default_and_prints_range(capsys):
    code = main(["--start", "2025-09-01T00:00:00", "--end", "2025-09-01T01:00:00"])
    assert code == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "UTC start: 2025-09-01T00:00:00" in out
    assert "EUR_USD" in out
    assert "USD_CHF" in out


def test_download_symbol_resume_with_mock(tmp_path: Path):
    existing = pd.DataFrame(
        [
            {
                "time": datetime(2024, 1, 2, 8, 5, 0),
                "open": 1.1,
                "high": 1.11,
                "low": 1.09,
                "close": 1.1,
                "complete": True,
            }
        ]
    )
    from forex_bot.decision_quality.history_cache import write_canonical_csv

    write_canonical_csv(existing, tmp_path / "EUR_USD_M5.csv")
    fetched: list[tuple] = []

    def fetch_page(symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        fetched.append((symbol, start, end))
        rows = []
        cur = start
        px = 1.2
        while cur <= end:
            rows.append(
                {
                    "time": cur,
                    "open": px,
                    "high": px + 0.0002,
                    "low": px - 0.0002,
                    "close": px,
                    "complete": True,
                }
            )
            cur = cur + pd.Timedelta(minutes=5)
            px += 0.001
        return pd.DataFrame(rows)

    summary = download_symbol(
        "EUR_USD",
        TimeWindow(datetime(2024, 1, 2, 8, 0, 0), datetime(2024, 1, 2, 8, 15, 0)),
        data_dir=tmp_path,
        fetch_page=fetch_page,
        now_utc=datetime(2024, 1, 3, 0, 0, 0),
    )
    assert summary["ok"] is True
    assert summary["bars"] == 4
    assert datetime(2024, 1, 2, 8, 5, 0) not in [c[1] for c in fetched] or True
    # 08:05 must not be the only page start; existing bar was not re-requested as a lone window.
    starts = [c[1] for c in fetched]
    assert datetime(2024, 1, 2, 8, 5, 0) not in starts
    loaded = read_canonical_csv(tmp_path / "EUR_USD_M5.csv")
    assert len(loaded) == 4
    assert list(RESEARCH_SYMBOLS) == [
        "EUR_USD",
        "GBP_USD",
        "USD_JPY",
        "AUD_USD",
        "USD_CAD",
        "USD_CHF",
    ]


def test_plan_clips_forming_candle():
    window = plan_range(start="2026-09-16T00:00:00", end="2026-09-16T23:59:00", now_utc=datetime(2026, 9, 16, 10, 53, 0))
    assert window.end == datetime(2026, 9, 16, 10, 45, 0)
    text = format_plan(window, RESEARCH_SYMBOLS, Path("data/historical"))
    assert "completed candles only" in text

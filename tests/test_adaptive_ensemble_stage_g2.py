"""Stage G.2 simulator, portfolio, source-safety and gate tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]
import pytest

from forex_bot.research.adaptive_ensemble.conversion import (
    GBP_CONVERSION_UNVERIFIED,
    FxQuote,
    RateTable,
    convert_pnl,
    fixture_table,
)
from forex_bot.research.adaptive_ensemble.isolation import forbidden_hits
from forex_bot.research.adaptive_ensemble.portfolio_v2 import (
    PortfolioV2,
    dumps,
    event_sort_key,
    load_portfolio,
    process_events,
    reserve,
)
from forex_bot.research.adaptive_ensemble.protocol import integrity_hash, load_protocol
from forex_bot.research.adaptive_ensemble.provenance import sha256_bytes
from forex_bot.research.adaptive_ensemble.quality_gates import (
    complete_trading_days_after,
    duration_status,
    gate_dataset,
)
from forex_bot.research.adaptive_ensemble.simulate import fill_price as fill_v1
from forex_bot.research.adaptive_ensemble.simulator_v2 import (
    WARMUP_BARS,
    entry_fill,
    executable,
    mark_exit_v2,
    warmup_reason,
)
from forex_bot.research.adaptive_ensemble.source_audit import (
    DATA_SOURCE_REQUIRES_OPERATOR_APPROVAL,
    source_audit,
)

REPORTED_HASH = "539cdc083f83393a79d254d21385edc6c48e88eb0f085d4549df9fdd6d431bc0"


def _bar(ts: str, o: float, h: float, l: float, c: float, spread: float, atr: float = 0.0004) -> dict:
    half = spread / 2.0
    return {
        "time": ts,
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "bid_open": o - half,
        "ask_open": o + half,
        "bid_high": h - half,
        "ask_high": h + half,
        "bid_low": l - half,
        "ask_low": l + half,
        "bid_close": c - half,
        "ask_close": c + half,
        "feat_atr": atr,
        "feat_h1_dir": 1.0,
    }


def test_protocol_hash_and_no_broker_calls() -> None:
    proto = load_protocol()
    assert proto["integrity_hash"] == REPORTED_HASH
    assert integrity_hash(proto) == REPORTED_HASH
    audit = source_audit()
    assert audit["broker_api_calls_made"] is False
    assert audit["status"] == DATA_SOURCE_REQUIRES_OPERATOR_APPROVAL
    assert audit["credentials_read"] is False


def test_no_credential_literals_in_research_package() -> None:
    root = Path("forex_bot/research/adaptive_ensemble")
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "OANDA-" not in text
        assert "Bearer " not in text


def test_raw_hash_and_overlap_zero_after_cutoff() -> None:
    assert sha256_bytes(b"x") != sha256_bytes(b"y")
    df = pd.DataFrame({"time": ["2026-08-31T23:50:00Z"]})
    assert complete_trading_days_after(df) == 0
    assert duration_status(0) == "INSUFFICIENT_INDEPENDENT_DURATION"


def test_no_mid_fallback_and_buy_sell_entry() -> None:
    rows = [_bar("2026-09-01T12:00:00Z", 1.10, 1.101, 1.099, 1.10, 0.0002) for _ in range(3)]
    rows[1]["ask_open"] = 1.10012
    rows[1]["bid_open"] = 1.09988
    df = pd.DataFrame(rows)
    buy, err = entry_fill(df, 1, "BUY", "base")
    sell, err2 = entry_fill(df, 1, "SELL", "base")
    assert err is None and err2 is None
    assert buy == pytest.approx(1.10012)
    assert sell == pytest.approx(1.09988)
    bare = pd.DataFrame({"open": [1.1], "high": [1.11], "low": [1.09], "close": [1.1], "feat_atr": [0.0004]})
    px, why = entry_fill(bare, 0, "BUY", "base")
    assert px is None and why == "missing_ask"
    v1 = fill_v1(bare, 0, "BUY", "base")
    assert v1 is not None


def test_warmup_and_h1() -> None:
    df = pd.DataFrame([_bar("2026-09-01T12:00:00Z", 1.1, 1.11, 1.09, 1.1, 0.0002)] * 130)
    assert warmup_reason(df, 50) == "insufficient_warmup"
    assert WARMUP_BARS == 120
    df.loc[120, "feat_h1_dir"] = float("nan")
    assert warmup_reason(df, 120) == "h1_incomplete"
    df.loc[120, "feat_h1_dir"] = 1.0
    assert warmup_reason(df, 120) is None


def test_gap_stop_uses_open_not_stop() -> None:
    rows = [_bar("2026-09-01T12:00:00Z", 1.10, 1.101, 1.099, 1.10, 0.0002) for _ in range(3)]
    rows[2]["bid_open"] = 1.07
    rows[2]["ask_open"] = 1.0702
    rows[2]["bid_low"] = 1.06
    rows[2]["bid_high"] = 1.075
    rows[2]["bid_close"] = 1.07
    df = pd.DataFrame(rows)
    _i, px, why = mark_exit_v2(df, 2, "BUY", sl=1.09, tp=1.12, max_hold=24, cost="base")
    assert why == "gap_stop_executable_open"
    assert px == pytest.approx(1.07)


def test_gap_tp_capped_and_same_bar() -> None:
    rows = [_bar("2026-09-01T12:00:00Z", 1.10, 1.101, 1.099, 1.10, 0.0002) for _ in range(3)]
    rows[2]["bid_open"] = 1.13
    rows[2]["bid_high"] = 1.14
    rows[2]["bid_low"] = 1.12
    rows[2]["bid_close"] = 1.13
    df = pd.DataFrame(rows)
    _i, px, why = mark_exit_v2(df, 2, "BUY", sl=1.09, tp=1.11, max_hold=24, cost="base")
    assert why == "gap_target_capped_at_tp"
    assert px == pytest.approx(1.11)
    rows2 = [_bar("2026-09-01T12:00:00Z", 1.10, 1.12, 1.08, 1.10, 0.0002) for _ in range(3)]
    df2 = pd.DataFrame(rows2)
    _i, _px2, why2 = mark_exit_v2(df2, 2, "BUY", sl=1.09, tp=1.11, max_hold=24, cost="base")
    assert "conservative_sl" in why2 or why2 == "gap_stop_executable_open"


def test_slippage_adverse_not_double_spread() -> None:
    rows = [_bar("2026-09-01T12:00:00Z", 1.10, 1.101, 1.099, 1.10, 0.0002) for _ in range(3)]
    rows[1]["ask_open"] = 1.10010
    df = pd.DataFrame(rows)
    base, _ = entry_fill(df, 1, "BUY", "base")
    sev, _ = entry_fill(df, 1, "BUY", "severe")
    assert sev == pytest.approx((base or 0) + 0.50 * 0.0004)


def test_gbp_routes_jpy_identity_future_missing() -> None:
    table = fixture_table()
    when = datetime(2026, 9, 1, 12, 5, tzinfo=timezone.utc)
    eur = convert_pnl(pnl_quote=1.35, pair="EUR_USD", when=when, table=table)
    assert eur.gbp == pytest.approx(1.0)
    jpy = convert_pnl(pnl_quote=150.0, pair="USD_JPY", when=when, table=table)
    assert jpy.gbp == pytest.approx(1.0 / 1.35)
    ident = convert_pnl(pnl_quote=2.0, pair="EUR_GBP", when=when, table=table)
    assert ident.gbp == pytest.approx(2.0)
    late = RateTable([FxQuote(datetime(2026, 9, 2, tzinfo=timezone.utc), "GBP_USD", 1.2, 1.3, "late")])
    fut = convert_pnl(pnl_quote=1.0, pair="EUR_USD", when=when, table=late)
    assert fut.status == GBP_CONVERSION_UNVERIFIED
    miss = convert_pnl(pnl_quote=1.0, pair="EUR_USD", when=when, table=RateTable())
    assert miss.status == GBP_CONVERSION_UNVERIFIED


def test_model_state_still_fail_closed(tmp_path: Path) -> None:
    from forex_bot.research.adaptive_ensemble.state_v2 import (
        UNAVAILABLE,
        load_v2,
        model_dynamic_v2,
    )

    st = load_v2(tmp_path / "missing.json", fresh_run=False)
    assert st.status == UNAVAILABLE
    d = model_dynamic_v2(
        {
            "status": "ok",
            "regime": "trending",
            "ma_slope": 2e-5,
            "atr": 0.0004,
            "rsi": 55.0,
            "atr_pct": 0.5,
            "half_spread": 0.00006,
            "spread_over_atr": 0.1,
            "h1_dir": 1.0,
            "prior_high": 1.1,
            "prior_low": 1.09,
            "close": 1.105,
        },
        st,
    )
    assert d.direction == "NO_TRADE"


def test_simultaneous_signals_and_usd_cap() -> None:
    table = fixture_table()
    t = "2026-09-01T12:00:00+00:00"
    events = [
        {"kind": "signal", "pair": "EUR_USD", "direction": "BUY", "units": 1000, "time": t, "seq": 0},
        {"kind": "signal", "pair": "GBP_USD", "direction": "BUY", "units": 1000, "time": t, "seq": 0},
        {"kind": "fill", "pair": "EUR_USD", "entry": 1.1, "time": t, "seq": 1},
        {"kind": "fill", "pair": "GBP_USD", "entry": 1.3, "time": t, "seq": 1},
    ]
    st = process_events(events, run_id="p1", table=table)
    assert set(st.open) == {"EUR_USD", "GBP_USD"}
    st2 = PortfolioV2(run_id="p2")
    reserve(st2, pair="EUR_USD", direction="BUY", units=1500, time=t, event_id="a")
    blocked = reserve(st2, pair="USD_JPY", direction="SELL", units=1500, time=t, event_id="b")
    assert blocked == "shared_usd_cap"


def test_capital_pending_partial_and_missing_fx() -> None:
    t = "2026-09-01T12:00:00+00:00"
    st = process_events(
        [
            {"kind": "signal", "pair": "EUR_USD", "direction": "BUY", "units": 1000, "time": t, "seq": 0},
            {"kind": "fill", "pair": "EUR_USD", "entry": 1.1, "time": t, "seq": 1, "fraction": 0.5},
        ],
        run_id="p3",
        table=fixture_table(),
    )
    assert st.open["EUR_USD"].units == pytest.approx(500.0)
    st_m = process_events(
        [
            {"kind": "signal", "pair": "EUR_USD", "direction": "BUY", "units": 1000, "time": t, "seq": 0},
            {"kind": "fill", "pair": "EUR_USD", "entry": 1.1, "time": t, "seq": 1},
            {"kind": "exit", "pair": "EUR_USD", "exit_px": 1.11, "time": t, "seq": 2},
        ],
        run_id="p4",
        table=None,
    )
    assert st_m.conversion_status == GBP_CONVERSION_UNVERIFIED


def test_daily_loss_drawdown_restart() -> None:
    table = fixture_table()
    t0 = "2026-09-01T12:00:00+00:00"
    t1 = "2026-09-01T13:00:00+00:00"
    st = process_events(
        [
            {"kind": "signal", "pair": "EUR_USD", "direction": "BUY", "units": 1000, "time": t0, "seq": 0},
            {"kind": "fill", "pair": "EUR_USD", "entry": 1.10, "time": t0, "seq": 1},
            {"kind": "exit", "pair": "EUR_USD", "exit_px": 1.09, "time": t1, "seq": 2},
        ],
        run_id="p5",
        table=table,
    )
    assert st.halted in {"daily_loss", "max_drawdown"}
    blob = json.loads(dumps(st))
    loaded = load_portfolio(blob)
    assert loaded.halted == st.halted
    blob["realised_gbp"] = 0.0
    assert load_portfolio(blob).status == "MODEL_STATE_INVALID"


def test_event_order_deterministic() -> None:
    a = {"time": "t", "pair": "GBP_USD", "kind": "signal", "seq": 0}
    b = {"time": "t", "pair": "EUR_USD", "kind": "signal", "seq": 0}
    assert event_sort_key(b) < event_sort_key(a)


def test_duplicate_and_incomplete_quality() -> None:
    df = pd.DataFrame(
        {
            "time": ["2026-09-01T00:00:00Z", "2026-09-01T00:00:00Z"],
            "open": [1.1, 1.1],
            "high": [1.11, 1.11],
            "low": [1.09, 1.09],
            "close": [1.1, 1.1],
            "bid_close": [1.099, 1.099],
            "ask_close": [1.101, 1.101],
            "complete": [True, False],
        }
    )
    g = gate_dataset(df, pair="EUR_USD")
    assert g["status"] == "FAIL"


def test_unexpected_gap_not_dropped() -> None:
    times = list(pd.date_range("2026-09-01", periods=3, freq="5min", tz="UTC")) + [
        pd.Timestamp("2026-09-01 04:00", tz="UTC")
    ]
    df = pd.DataFrame(
        {
            "time": times,
            "open": [1.1] * 4,
            "high": [1.11] * 4,
            "low": [1.09] * 4,
            "close": [1.1] * 4,
            "bid_close": [1.099] * 4,
            "ask_close": [1.101] * 4,
        }
    )
    g = gate_dataset(df, pair="EUR_USD")
    assert g["unexpected_gaps"] >= 1
    assert g["rows"] == 4


def test_isolation_and_stage_g_artifacts() -> None:
    assert forbidden_hits() == {}
    assess = json.loads(Path("data/research/adaptive_ensemble/assessment.json").read_text(encoding="utf-8"))
    assert assess["assessment"] == "EXPLORATORY_NO_CREDIBLE_EDGE"
    g1 = json.loads(Path("data/research/adaptive_ensemble/g1/readiness_manifest.json").read_text(encoding="utf-8"))
    assert g1["classification"] == "VALIDATION_INFRASTRUCTURE_READY_DATA_PENDING"


def test_executable_never_uses_mid() -> None:
    row = pd.Series({"close": 1.25, "open": 1.24})
    assert executable(row, "ask", "open") is None
    assert executable(row, "bid", "close") is None

"""Stage G.1 validation-readiness tests. Broker interfaces disabled."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]
import pytest

from forex_bot.research.adaptive_ensemble.accounting import (
    drawdown_threshold,
    eur_usd_long_fixture,
    eur_usd_short_fixture,
    gap_through_stop_fixture,
    same_bar_ambiguity_fixture,
    slippage_fixture,
    usd_jpy_long_fixture,
    usd_jpy_short_fixture,
    utc_day_rollover,
)
from forex_bot.research.adaptive_ensemble.conversion import (
    GBP_CONVERSION_UNVERIFIED,
    FxQuote,
    RateTable,
    convert_pnl,
    fixture_table,
)
from forex_bot.research.adaptive_ensemble.importer import (
    DATA_SOURCE_REQUIRES_OPERATOR_APPROVAL,
    acquire_external_market_data,
    import_local_csv,
)
from forex_bot.research.adaptive_ensemble.isolation import forbidden_hits
from forex_bot.research.adaptive_ensemble.models import WeightState, model_dynamic
from forex_bot.research.adaptive_ensemble.portfolio import (
    PAIRS,
    PortfolioLimits,
    PortfolioState,
    align_clocks,
    can_open,
    readiness_assessment,
    usd_sign,
)
from forex_bot.research.adaptive_ensemble.protocol import (
    DEFAULT_PATH,
    integrity_hash,
    load_protocol,
)
from forex_bot.research.adaptive_ensemble.provenance import (
    PREVIOUSLY_EXAMINED,
    classify_period,
    overlap_with_stage_eg,
    sha256_bytes,
)
from forex_bot.research.adaptive_ensemble.quality import validate_frame
from forex_bot.research.adaptive_ensemble.state_v2 import (
    INCOMPATIBLE,
    INVALID,
    UNAVAILABLE,
    apply_delayed_outcomes_v2,
    enqueue_outcome_v2,
    initialise_fresh,
    load_v2,
    model_dynamic_v2,
    save_v2,
)

REPORTED_HASH = "539cdc083f83393a79d254d21385edc6c48e88eb0f085d4549df9fdd6d431bc0"


def _snap_ok() -> dict:
    return {
        "status": "ok",
        "regime": "trending",
        "ma_slope": 2e-5,
        "atr": 0.0004,
        "rsi": 55.0,
        "atr_pct": 0.5,
        "half_spread": 0.00006,
        "spread_over_atr": 0.1,
        "h1_dir": 1.0,
        "prior_high": 1.10,
        "prior_low": 1.09,
        "close": 1.105,
    }


def test_stage_g_protocol_hash_verified() -> None:
    proto = load_protocol()
    assert proto["integrity_hash"] == REPORTED_HASH
    assert integrity_hash(proto) == REPORTED_HASH
    assert proto["protocol_id"] == "stage_g_adaptive_ensemble_v1"


def test_stage_g_artifacts_not_rewritten_by_g1() -> None:
    assess = json.loads(Path("data/research/adaptive_ensemble/assessment.json").read_text(encoding="utf-8"))
    assert assess["assessment"] == "EXPLORATORY_NO_CREDIBLE_EDGE"
    assert DEFAULT_PATH.is_file()


def test_hash_validation_detects_bytes_change() -> None:
    assert sha256_bytes(b"a") != sha256_bytes(b"b")


def test_overlap_detection_stage_eg() -> None:
    s = pd.Series(["2026-08-31T23:50:00Z", "2026-09-01T00:00:00Z"])
    ov = overlap_with_stage_eg(s)
    assert ov["overlap_n"] == 1
    assert ov["new_after_n"] == 1
    assert classify_period(
        datetime(2025, 9, 1, tzinfo=timezone.utc),
        datetime(2026, 8, 31, 23, 50, tzinfo=timezone.utc),
        exposed=True,
    ) == PREVIOUSLY_EXAMINED


def test_candle_integrity_and_duplicates() -> None:
    df = pd.DataFrame(
        {
            "time": ["2026-09-01T00:00:00Z", "2026-09-01T00:00:00Z"],
            "open": [1.1, 1.1],
            "high": [1.2, 1.2],
            "low": [1.0, 1.0],
            "close": [1.1, 1.1],
            "bid_close": [1.099, 1.099],
            "ask_close": [1.101, 1.101],
        }
    )
    rep = validate_frame(df, pair="EUR_USD")
    assert rep["status"] == "FAIL"
    assert rep["duplicate_timestamps"] == 1


def test_missing_bars_and_weekend() -> None:
    times = pd.date_range("2026-09-04", periods=3, freq="5min", tz="UTC")  # Friday
    times = times.append(pd.DatetimeIndex([pd.Timestamp("2026-09-06 21:00", tz="UTC")]))  # Sunday 21:00
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
    rep = validate_frame(df, pair="EUR_USD")
    assert rep["weekend_or_closure_gaps"] >= 1


def test_dst_utc_grid_is_stable() -> None:
    times = pd.date_range("2026-03-29 00:00", periods=24, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "time": times,
            "open": [1.1] * 24,
            "high": [1.11] * 24,
            "low": [1.09] * 24,
            "close": [1.1] * 24,
            "bid_close": [1.099] * 24,
            "ask_close": [1.101] * 24,
        }
    )
    rep = validate_frame(df, pair="EUR_USD")
    assert rep["dst_odd_spacing"] == 0
    assert rep["duplicate_timestamps"] == 0


def test_incomplete_and_spread_invalid() -> None:
    df = pd.DataFrame(
        {
            "time": ["2026-09-01T00:00:00Z"],
            "open": [1.1],
            "high": [1.11],
            "low": [1.09],
            "close": [1.1],
            "complete": [False],
            "bid_close": [1.2],
            "ask_close": [1.1],
        }
    )
    rep = validate_frame(df, pair="EUR_USD")
    assert rep["status"] == "FAIL"
    assert rep["incomplete_candles"] == 1
    assert rep["spread_invalid"] == 1


def test_conversion_eur_and_usd_jpy() -> None:
    table = fixture_table()
    when = datetime(2026, 9, 1, 12, 5, tzinfo=timezone.utc)
    eur = convert_pnl(pnl_quote=1.35, pair="EUR_USD", when=when, table=table)
    assert eur.status == "ok"
    assert eur.gbp == pytest.approx(1.0)
    jpy = convert_pnl(pnl_quote=150.0, pair="USD_JPY", when=when, table=table)
    assert jpy.status == "ok"
    assert jpy.gbp == pytest.approx(150.0 / 150.0 / 1.35)


def test_no_future_conversion() -> None:
    table = RateTable(
        [FxQuote(datetime(2026, 9, 2, tzinfo=timezone.utc), "GBP_USD", 1.2, 1.3, "late")]
    )
    r = convert_pnl(
        pnl_quote=1.0,
        pair="EUR_USD",
        when=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        table=table,
    )
    assert r.status == GBP_CONVERSION_UNVERIFIED
    assert r.gbp is None


def test_missing_conversion() -> None:
    r = convert_pnl(
        pnl_quote=1.0,
        pair="EUR_USD",
        when=datetime(2026, 9, 1, tzinfo=timezone.utc),
        table=RateTable(),
    )
    assert r.status == GBP_CONVERSION_UNVERIFIED


def test_accounting_long_short_jpy() -> None:
    el = eur_usd_long_fixture()
    assert el["entry"] == pytest.approx(el["expected_entry"])
    assert el["exit_px"] == pytest.approx(el["expected_exit"])
    assert el["pnl_quote"] == pytest.approx(el["expected_pnl_quote"])
    es = eur_usd_short_fixture()
    assert es["pnl_quote"] == pytest.approx(es["expected_pnl_quote"])
    jl = usd_jpy_long_fixture()
    assert jl["pnl_quote"] == pytest.approx(jl["expected_pnl_quote"])
    js = usd_jpy_short_fixture()
    assert js["pnl_quote"] == pytest.approx(js["expected_pnl_quote"])


def test_same_bar_and_gap_and_slippage() -> None:
    amb = same_bar_ambiguity_fixture()
    assert amb["why"] == amb["expected_why"]
    assert amb["exit_px"] == pytest.approx(amb["expected_px"])
    gap = gap_through_stop_fixture()
    assert gap["why"] == "stop_loss"
    slip = slippage_fixture()
    assert slip["severe"] == pytest.approx(slip["expected_severe"])


def test_drawdown_and_utc_rollover() -> None:
    dd = drawdown_threshold()
    assert dd["halt"] == "max_drawdown"
    days = utc_day_rollover()
    assert days["day_a"] == days["expected_a"]
    assert days["day_b"] == days["expected_b"]


def test_fresh_run_versus_restart(tmp_path: Path) -> None:
    p = tmp_path / "w.json"
    missing = load_v2(p, fresh_run=False)
    assert missing.status == UNAVAILABLE
    d = model_dynamic_v2(_snap_ok(), missing)
    assert d.direction == "NO_TRADE"
    assert d.reason == UNAVAILABLE
    fresh = load_v2(p, fresh_run=True, run_id="run-a")
    assert fresh.status == "ok"
    save_v2(fresh, p)
    again = load_v2(p, fresh_run=False)
    assert again.weights == fresh.weights
    assert again.run_id == "run-a"


def test_corrupt_and_incompatible_state(tmp_path: Path) -> None:
    p = tmp_path / "w.json"
    p.write_text("{", encoding="utf-8")
    assert load_v2(p).status == INVALID
    p.write_text("{}", encoding="utf-8")
    assert load_v2(p).status in {INVALID, INCOMPATIBLE}
    st = initialise_fresh(run_id="run-b")
    save_v2(st, p)
    blob = json.loads(p.read_text(encoding="utf-8"))
    blob["weights"]["proxy_trend_ma_slope_v1"] = 1.7
    p.write_text(json.dumps(blob), encoding="utf-8")
    assert load_v2(p).status == INVALID
    st2 = initialise_fresh(run_id="run-c")
    save_v2(st2, p)
    blob = json.loads(p.read_text(encoding="utf-8"))
    blob["schema"] = "exp_weights_v1"
    blob["integrity_hash"] = "x"
    p.write_text(json.dumps(blob), encoding="utf-8")
    assert load_v2(p).status == INCOMPATIBLE


def test_invalid_weights_and_candidate_set(tmp_path: Path) -> None:
    st = initialise_fresh(run_id="run-d")
    p = tmp_path / "w.json"
    save_v2(st, p)
    blob = json.loads(p.read_text(encoding="utf-8"))
    blob["weights"]["proxy_trend_ma_slope_v1"] = -1.0
    from forex_bot.research.adaptive_ensemble.protocol import integrity_hash as ih

    blob["integrity_hash"] = ih(blob)
    p.write_text(json.dumps(blob), encoding="utf-8")
    assert load_v2(p).status == INVALID


def test_duplicate_and_delayed_feedback(tmp_path: Path) -> None:
    st = initialise_fresh(run_id="run-e")
    enqueue_outcome_v2(st, candidate_id="proxy_trend_ma_slope_v1", ready_i=10, pnl=1.0, feedback_id="f1")
    enqueue_outcome_v2(st, candidate_id="proxy_trend_ma_slope_v1", ready_i=10, pnl=1.0, feedback_id="f1")
    apply_delayed_outcomes_v2(st, 9)
    assert st.updates == 0
    apply_delayed_outcomes_v2(st, 10)
    assert st.updates == 1
    before = st.weights["proxy_trend_ma_slope_v1"]
    enqueue_outcome_v2(st, candidate_id="proxy_trend_ma_slope_v1", ready_i=10, pnl=1.0, feedback_id="f1")
    apply_delayed_outcomes_v2(st, 10)
    assert st.weights["proxy_trend_ma_slope_v1"] == before
    p = tmp_path / "w.json"
    save_v2(st, p)
    loaded = load_v2(p)
    assert loaded.updates == 1
    assert loaded.weights["proxy_trend_ma_slope_v1"] == pytest.approx(before)


def test_v1_silent_reset_preserved(tmp_path: Path) -> None:
    p = tmp_path / "old.json"
    p.write_text("{}", encoding="utf-8")
    st = WeightState.load(p)
    assert st.weights["proxy_trend_ma_slope_v1"] == 1.0
    d = model_dynamic(_snap_ok(), st)
    assert d.model_id == "dynamic_weights"


def test_truncated_state_fail_closed(tmp_path: Path) -> None:
    st = initialise_fresh(run_id="run-f")
    p = tmp_path / "w.json"
    save_v2(st, p)
    text = p.read_text(encoding="utf-8")
    p.write_text(text[:20], encoding="utf-8")
    bad = load_v2(p, fresh_run=False)
    assert bad.status == INVALID
    assert model_dynamic_v2(_snap_ok(), bad).reason == INVALID


def test_atomic_write_leaves_destination_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    st = initialise_fresh(run_id="run-g")
    p = tmp_path / "w.json"
    save_v2(st, p)
    original = p.read_text(encoding="utf-8")

    def boom(*_a: object, **_k: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("forex_bot.research.adaptive_ensemble.state_v2.os.replace", boom)
    with pytest.raises(OSError):
        st.updates = 3
        save_v2(st, p)
    assert p.read_text(encoding="utf-8") == original


def test_multi_pair_caps_and_alignment() -> None:
    st = PortfolioState(nav=97.0, peak=97.0)
    lim = PortfolioLimits()
    assert can_open(st, lim, "EUR_USD", "BUY", 1000) is None
    st.open["EUR_USD"] = type("S", (), {"pair": "EUR_USD", "direction": "BUY", "units": 1000.0, "usd_sign": usd_sign("EUR_USD", "BUY")})()
    assert can_open(st, lim, "EUR_USD", "BUY", 1000) == "duplicate_pair_exposure"
    clocks = align_clocks({"EUR_USD": ["t1", "t2"], "GBP_USD": ["t1"]})
    assert clocks["tie_break_order"] == PAIRS
    assert readiness_assessment()["status"] == "MULTI_PAIR_VALIDATION_NOT_READY"


def test_external_import_not_invoked() -> None:
    r = acquire_external_market_data(pair="EUR_USD", after_iso="2026-08-31T23:50:00Z")
    assert r.status == DATA_SOURCE_REQUIRES_OPERATOR_APPROVAL
    assert r.frame is None


def test_local_import_marks_previously_examined() -> None:
    path = Path("data/historical/EUR_USD_M5.csv")
    if not path.is_file():
        pytest.skip("historical csv missing")
    imported = import_local_csv(path, pair="EUR_USD")
    assert imported.provenance["independence_label"] == PREVIOUSLY_EXAMINED
    assert imported.provenance["overlap_stage_eg"]["new_after_n"] == 0


def test_broker_isolation() -> None:
    assert forbidden_hits() == {}


def test_g1_does_not_import_live_safety() -> None:
    from forex_bot.research.adaptive_ensemble import isolation

    mods = isolation.imported_modules(Path(isolation.__file__).with_name("g1_runner.py"))
    assert "forex_bot.live_safety" not in mods
    assert "forex_bot.oanda_exec" not in mods

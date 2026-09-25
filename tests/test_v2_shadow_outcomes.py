"""Idempotent V2 outcome persistence. Temporary stores only. No live scoring."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest

from forex_bot.v2_shadow.contract import ShadowOutcome
from forex_bot.v2_shadow.isolation import forbidden_hits_in_source
from forex_bot.v2_shadow.observe import build_observation
from forex_bot.v2_shadow.score import HORIZONS_MIN, score_shadow_decision
from forex_bot.v2_shadow.store import (
    STATUS_ALREADY_EXISTS,
    STATUS_CONFLICT,
    STATUS_STORE_UNSAFE,
    STATUS_WRITTEN,
    append_outcome,
    observations_path,
    outcomes_path,
    reset_outcome_index_cache,
)


def _side(pips: float, *, buy: bool = True) -> dict:
    entry = 1.10020 if buy else 1.10000
    future = entry + (pips * 0.0001 if buy else -pips * 0.0001)
    return {
        "status": "AVAILABLE",
        "entry": entry,
        "future_close": future,
        "forward_pips": pips,
        "forward_return": pips * 0.0001 / entry,
        "forward_r": None,
        "direction_correct": pips > 0,
        "mfe_pips": None,
        "mae_pips": None,
        "mfe_source": "research_bid_ask_path",
        "estimated_cost": 2.0,
        "net_after_cost": pips,
        "entry_side": "ask" if buy else "bid",
        "exit_side": "bid" if buy else "ask",
    }


def _horizon(pips_buy: float | None = 1.0, pips_sell: float | None = -1.0) -> dict:
    blob: dict = {}
    skip = {}
    if pips_buy is not None:
        blob["buy"] = _side(pips_buy, buy=True)
        skip["buy_would_cover_cost"] = pips_buy > 0
    if pips_sell is not None:
        blob["sell"] = _side(pips_sell, buy=False)
        skip["sell_would_cover_cost"] = pips_sell > 0
    blob["skip_opportunity"] = skip
    return blob


def _outcome(
    decision_id: str,
    horizons: dict,
    scored_at: str = "2026-09-24T13:00:00+00:00",
) -> ShadowOutcome:
    return ShadowOutcome(
        decision_id=decision_id,
        scored_at_utc=scored_at,
        model_name="v2_none",
        model_version="0",
        horizons=horizons,
        notes=["research_executable_side", "not_production_mfe", "proposed_action=SKIP"],
    )


def _lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


@pytest.fixture(autouse=True)
def _reset_index():
    reset_outcome_index_cache()
    yield
    reset_outcome_index_cache()


def test_empty_store_accepts_first_outcome(tmp_path):
    out = _outcome("v2sh_a", {"5": _horizon()})
    result = append_outcome(out, store_dir=tmp_path)
    assert result.status == STATUS_WRITTEN
    assert len(_lines(outcomes_path(tmp_path))) == 1


def test_identical_outcome_appended_twice_one_record(tmp_path):
    first = _outcome("v2sh_a", {"5": _horizon()}, scored_at="2026-09-24T13:00:00+00:00")
    second = _outcome("v2sh_a", {"5": _horizon()}, scored_at="2026-09-24T14:00:00+00:00")
    assert append_outcome(first, store_dir=tmp_path).status == STATUS_WRITTEN
    assert append_outcome(second, store_dir=tmp_path).status == STATUS_ALREADY_EXISTS
    assert len(_lines(outcomes_path(tmp_path))) == 1


def test_same_decision_different_horizon_both_retained(tmp_path):
    a = _outcome("v2sh_a", {"5": _horizon(1.0, None)})
    b = _outcome("v2sh_a", {"15": _horizon(2.0, None)})
    assert append_outcome(a, store_dir=tmp_path).status == STATUS_WRITTEN
    assert append_outcome(b, store_dir=tmp_path).status == STATUS_WRITTEN
    assert len(_lines(outcomes_path(tmp_path))) == 2


def test_same_decision_horizon_buy_and_sell_both_retained(tmp_path):
    buy = _outcome("v2sh_a", {"5": _horizon(1.0, None)})
    sell = _outcome("v2sh_a", {"5": _horizon(None, -1.0)})
    assert append_outcome(buy, store_dir=tmp_path).status == STATUS_WRITTEN
    assert append_outcome(sell, store_dir=tmp_path).status == STATUS_WRITTEN
    assert len(_lines(outcomes_path(tmp_path))) == 2


def test_reload_protects_existing_key(tmp_path):
    out = _outcome("v2sh_a", {"5": _horizon()})
    assert append_outcome(out, store_dir=tmp_path).status == STATUS_WRITTEN
    reset_outcome_index_cache()
    again = _outcome("v2sh_a", {"5": _horizon()}, scored_at="2026-09-24T18:00:00+00:00")
    assert append_outcome(again, store_dir=tmp_path).status == STATUS_ALREADY_EXISTS
    assert len(_lines(outcomes_path(tmp_path))) == 1


def test_conflicting_payload_not_appended(tmp_path):
    first = _outcome("v2sh_a", {"5": _horizon(1.0, None)})
    conflict = _outcome("v2sh_a", {"5": _horizon(9.0, None)})
    assert append_outcome(first, store_dir=tmp_path).status == STATUS_WRITTEN
    result = append_outcome(conflict, store_dir=tmp_path)
    assert result.status == STATUS_CONFLICT
    rows = [json.loads(ln) for ln in _lines(outcomes_path(tmp_path))]
    assert len(rows) == 1
    assert rows[0]["horizons"]["5"]["buy"]["forward_pips"] == pytest.approx(1.0)


def test_concurrent_same_key_one_record(tmp_path):
    out = _outcome("v2sh_conc", {"30": _horizon()})
    barrier = threading.Barrier(2)
    results: list[str] = []

    def worker() -> None:
        barrier.wait()
        results.append(append_outcome(out, store_dir=tmp_path).status)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [STATUS_ALREADY_EXISTS, STATUS_WRITTEN]
    assert len(_lines(outcomes_path(tmp_path))) == 1


def test_malformed_historical_json_fails_closed(tmp_path):
    path = outcomes_path(tmp_path)
    path.write_text("{not-json\n", encoding="utf-8")
    reset_outcome_index_cache()
    result = append_outcome(_outcome("v2sh_a", {"5": _horizon()}), store_dir=tmp_path)
    assert result.status == STATUS_STORE_UNSAFE
    assert path.read_text(encoding="utf-8") == "{not-json\n"


def test_truncated_final_line_fails_closed(tmp_path):
    path = outcomes_path(tmp_path)
    path.write_text('{"decision_id":"v2sh_x","horizons":{"5":{"buy":{"status":"AVAILABLE"}', encoding="utf-8")
    reset_outcome_index_cache()
    result = append_outcome(_outcome("v2sh_a", {"5": _horizon()}), store_dir=tmp_path)
    assert result.status == STATUS_STORE_UNSAFE
    assert "AVAILABLE" in path.read_text(encoding="utf-8")
    assert len(_lines(path)) == 1
    assert not path.read_text(encoding="utf-8").endswith("}\n")


def test_observations_jsonl_untouched(tmp_path):
    obs_path = observations_path(tmp_path)
    obs_path.write_text('{"decision_id":"keep-me"}\n', encoding="utf-8")
    append_outcome(_outcome("v2sh_a", {"5": _horizon()}), store_dir=tmp_path)
    assert obs_path.read_text(encoding="utf-8") == '{"decision_id":"keep-me"}\n'


def test_market_jsonl_untouched(tmp_path):
    market = tmp_path / "market" / "EUR_USD_M5.jsonl"
    market.parent.mkdir(parents=True)
    market.write_text('{"symbol":"EUR_USD","complete":true}\n', encoding="utf-8")
    append_outcome(_outcome("v2sh_a", {"5": _horizon()}), store_dir=tmp_path)
    assert market.read_text(encoding="utf-8") == '{"symbol":"EUR_USD","complete":true}\n'


def test_scorer_executable_semantics_unchanged():
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
    t0 = datetime(2026, 9, 21, 22, 0, tzinfo=timezone.utc)
    bars = []
    bid = 1.10000
    ask = 1.10020
    for i in range(50):
        bid += 0.00010
        ask += 0.00010
        ts = datetime.fromtimestamp(t0.timestamp() + (i + 1) * 300, tz=timezone.utc).isoformat()
        bars.append(
            {
                "ts": ts,
                "bid_high": bid + 0.00005,
                "bid_low": bid - 0.00005,
                "bid_close": bid,
                "ask_high": ask + 0.00005,
                "ask_low": ask - 0.00005,
                "ask_close": ask,
            }
        )
    out = score_shadow_decision(obs, bars)
    assert HORIZONS_MIN == (5, 15, 30, 60, 120, 240)
    assert set(out.horizons) == {str(h) for h in HORIZONS_MIN}
    buy = out.horizons["5"]["buy"]
    sell = out.horizons["5"]["sell"]
    assert buy["entry_side"] == "ask"
    assert buy["exit_side"] == "bid"
    assert sell["entry_side"] == "bid"
    assert sell["exit_side"] == "ask"
    assert buy["direction_correct"] is (buy["forward_pips"] > 0)
    assert sell["direction_correct"] is (sell["forward_pips"] > 0)
    assert "buy_would_cover_cost" in out.horizons["5"]["skip_opportunity"]
    assert "sell_would_cover_cost" in out.horizons["5"]["skip_opportunity"]
    src = Path("forex_bot/v2_shadow/score.py").read_text(encoding="utf-8")
    assert "HORIZONS_MIN = (5, 15, 30, 60, 120, 240)" in src
    assert "direction_correct\": None if fwd is None else bool(fwd > 0)" in src or "bool(fwd > 0)" in src


def test_no_oanda_or_live_scoring_introduced():
    src = Path("forex_bot/v2_shadow/store.py").read_text(encoding="utf-8")
    assert forbidden_hits_in_source(src) == []
    assert "oanda_client" not in src
    assert "InstrumentsCandles" not in src
    loop = Path("forex_bot/bot_loop.py").read_text(encoding="utf-8")
    assert "append_outcome" not in loop
    assert "score_shadow_decision" not in loop
    assert "score_offline" not in loop
    assert "run_offline_score_pass" not in loop


def test_blank_lines_do_not_fail_index(tmp_path):
    first = append_outcome(_outcome("v2sh_a", {"5": _horizon()}), store_dir=tmp_path)
    assert first.status == STATUS_WRITTEN
    path = outcomes_path(tmp_path)
    path.write_text(path.read_text(encoding="utf-8") + "\n\n", encoding="utf-8")
    reset_outcome_index_cache()
    again = append_outcome(_outcome("v2sh_a", {"5": _horizon()}), store_dir=tmp_path)
    assert again.status == STATUS_ALREADY_EXISTS

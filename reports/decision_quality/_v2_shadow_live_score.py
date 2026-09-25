"""Offline first live V2 scoring pass. Local JSONL only. Not imported by bot_loop."""

from __future__ import annotations

import json
import statistics
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from forex_bot.v2_shadow.score import HORIZONS_MIN
from forex_bot.v2_shadow.score_offline import (
    decision_from_record,
    last_completed_m5_start,
    load_market_bars,
    load_observation_records,
    run_offline_score_pass,
    score_decision_against_market,
    summarize_persisted_outcomes,
)
from forex_bot.v2_shadow.market import market_dir as _market_dir
from forex_bot.v2_shadow.store import default_store_dir, observations_path, reset_outcome_index_cache


def _stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "hit": None, "mean": None, "median": None}
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
    }


def _label_table(rows: list[dict], opportunities: dict[str, str] | None = None) -> dict:
    """rows are persisted outcomes. If opportunities provided, keep earliest decision_id per key."""
    chosen = rows
    if opportunities is not None:
        keep = set(opportunities.values())
        chosen = [r for r in rows if r.get("decision_id") in keep]
    out: dict[str, dict] = {}
    for hz in HORIZONS_MIN:
        buys: list[float] = []
        sells: list[float] = []
        buy_hits = 0
        sell_hits = 0
        for row in chosen:
            blob = (row.get("horizons") or {}).get(str(hz)) or {}
            buy = blob.get("buy") or {}
            sell = blob.get("sell") or {}
            if buy.get("status") == "AVAILABLE" and buy.get("forward_pips") is not None:
                p = float(buy["forward_pips"])
                buys.append(p)
                buy_hits += int(bool(buy.get("direction_correct")))
            if sell.get("status") == "AVAILABLE" and sell.get("forward_pips") is not None:
                p = float(sell["forward_pips"])
                sells.append(p)
                sell_hits += int(bool(sell.get("direction_correct")))
        b = _stats(buys)
        s = _stats(sells)
        pairs = min(len(buys), len(sells))
        symmetry = None
        if pairs:
            symmetry = statistics.fmean([buys[i] + sells[i] for i in range(pairs)])
        out[str(hz)] = {
            "buy_n": b["n"],
            "buy_hit": None if not buys else buy_hits / len(buys),
            "buy_mean_pips": b["mean"],
            "buy_median_pips": b["median"],
            "sell_n": s["n"],
            "sell_hit": None if not sells else sell_hits / len(sells),
            "sell_mean_pips": s["mean"],
            "sell_median_pips": s["median"],
            "buy_plus_sell_mean_pips": symmetry,
        }
    return out


def _coverage(obs_rows: list[dict], outcomes: list[dict], market_bars: dict) -> dict:
    from forex_bot.v2_shadow.score_offline import horizon_has_terminal_bar, _ts

    by_id = {r["decision_id"]: r for r in outcomes}
    cov = {str(h): {"eligible": 0, "scored": 0, "missing_future": 0} for h in HORIZONS_MIN}
    by_symbol: dict[str, dict] = {}
    for rec in obs_rows:
        symbol = rec.get("symbol") or "?"
        bars = market_bars.get(symbol) or []
        start = _ts(rec.get("timestamp_utc"))
        bucket = by_symbol.setdefault(
            symbol, {str(h): {"eligible": 0, "scored": 0, "missing_future": 0} for h in HORIZONS_MIN}
        )
        persisted = by_id.get(rec.get("decision_id")) or {}
        for h in HORIZONS_MIN:
            hz = str(h)
            ok = start is not None and horizon_has_terminal_bar(start, h, bars)
            scored = bool(((persisted.get("horizons") or {}).get(hz) or {}).get("buy", {}).get("status") == "AVAILABLE")
            if ok:
                cov[hz]["eligible"] += 1
                bucket[hz]["eligible"] += 1
                if scored:
                    cov[hz]["scored"] += 1
                    bucket[hz]["scored"] += 1
            else:
                cov[hz]["missing_future"] += 1
                bucket[hz]["missing_future"] += 1
    return {"overall": cov, "by_symbol": by_symbol}


def _unique_opportunities(obs_rows: list[dict]) -> tuple[dict[str, str], int]:
    from forex_bot.v2_shadow.score_offline import _ts

    earliest: dict[str, tuple[datetime, str]] = {}
    for rec in obs_rows:
        ts = _ts(rec.get("timestamp_utc"))
        if ts is None:
            continue
        key = f"{rec.get('symbol')}|{last_completed_m5_start(ts).isoformat()}"
        prev = earliest.get(key)
        if prev is None or ts < prev[0]:
            earliest[key] = (ts, rec["decision_id"])
    return {k: v[1] for k, v in earliest.items()}, len(obs_rows)


def _rl_complete(rec: dict) -> bool:
    rl = rec.get("rl") or {}
    q = rl.get("q_values")
    return all(
        [
            rl.get("action") is not None,
            rl.get("state") is not None,
            rl.get("agree") is not None,
            rl.get("veto") is not None,
            isinstance(q, dict) and {"BUY", "SELL", "SKIP"} <= set(q),
            rl.get("epsilon") is not None,
        ]
    )


def validate_sample(root: Path, obs_rows: list[dict], market_bars: dict, n: int = 3) -> dict:
    sample_ids = [r["decision_id"] for r in obs_rows[:n]]
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "market").mkdir()
        # Use the real market + real observations via explicit paths; persist to tmp.
        reset_outcome_index_cache()
        report = run_offline_score_pass(
            store_dir=tmp_path,
            observations_file=observations_path(root),
            market_root=_market_dir(root),
            observation_ids=sample_ids,
            scored_at_utc="2026-09-24T21:00:00+00:00",
        )
        outcomes = summarize_persisted_outcomes(tmp_path)
        checks = []
        for row in outcomes:
            for hz, blob in (row.get("horizons") or {}).items():
                buy = blob.get("buy") or {}
                sell = blob.get("sell") or {}
                if buy:
                    checks.append(buy.get("entry_side") == "ask" and buy.get("exit_side") == "bid")
                if sell:
                    checks.append(sell.get("entry_side") == "bid" and sell.get("exit_side") == "ask")
        reset_outcome_index_cache()
        return {
            "ids": sample_ids,
            "written": report["written"],
            "conflicts": report["conflicts"],
            "executable_sides_ok": bool(checks) and all(checks),
            "outcomes": len(outcomes),
        }


def main() -> dict:
    root = default_store_dir()
    obs_rows, obs_mal = load_observation_records(observations_path(root))
    market = load_market_bars(_market_dir(root))
    sample = validate_sample(root, obs_rows, market["bars"])
    if not sample["executable_sides_ok"] or sample["conflicts"] or sample["written"] < 1:
        return {"stopped": True, "reason": "sample validation failed", "sample": sample}

    reset_outcome_index_cache()
    first = run_offline_score_pass(store_dir=root, scored_at_utc="2026-09-24T21:40:00+00:00")
    if first["conflicts"] or first["unsafe"]:
        return {"stopped": True, "reason": "first pass conflict/unsafe", "first": first, "sample": sample}

    reset_outcome_index_cache()
    second = run_offline_score_pass(store_dir=root, scored_at_utc="2026-09-24T21:41:00+00:00")
    if second["conflicts"] or second["written"] or second["unsafe"]:
        return {"stopped": True, "reason": "second pass not idempotent", "first": first, "second": second}

    outcomes = summarize_persisted_outcomes(root)
    opp_map, obs_n = _unique_opportunities(obs_rows)
    scored_ids = {r["decision_id"] for r in outcomes}
    scored_obs = [r for r in obs_rows if r.get("decision_id") in scored_ids]
    rl_n = sum(1 for r in scored_obs if _rl_complete(r))
    payload = {
        "stopped": False,
        "sample": sample,
        "first": {k: first[k] for k in first if k != "statuses"},
        "second": {k: second[k] for k in second if k != "statuses"},
        "observation_count": len(obs_rows),
        "observation_malformed": obs_mal,
        "unique_decision_ids": len({r.get("decision_id") for r in obs_rows}),
        "observation_range": [obs_rows[0]["timestamp_utc"], obs_rows[-1]["timestamp_utc"]] if obs_rows else [],
        "market": market["by_symbol"],
        "market_malformed": market["malformed"],
        "market_duplicates": market["duplicates"],
        "coverage": _coverage(obs_rows, outcomes, market["bars"]),
        "unique_opportunities": len(opp_map),
        "repeat_pct": None if not obs_n else 100.0 * (obs_n - len(opp_map)) / obs_n,
        "label_health_observation": _label_table(outcomes),
        "label_health_dedup": _label_table(outcomes, opp_map),
        "rl_complete_scored": rl_n,
        "rl_scored_obs": len(scored_obs),
        "outcome_rows": len(outcomes),
    }
    dest = Path("reports/decision_quality/_v2_shadow_live_score_results.json")
    dest.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in payload if k not in ("coverage",)}, indent=2, default=str))
    return payload


if __name__ == "__main__":
    main()

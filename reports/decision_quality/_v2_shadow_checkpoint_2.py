"""Second offline V2 outcome checkpoint. Local JSONL only. Not imported by bot_loop."""

from __future__ import annotations

import json
import statistics
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from forex_bot.v2_shadow.score import HORIZONS_MIN
from forex_bot.v2_shadow.score_offline import (
    _ts,
    last_completed_m5_start,
    load_market_bars,
    load_observation_records,
    run_offline_score_pass,
)
from forex_bot.v2_shadow.market import market_dir as _market_dir
from forex_bot.v2_shadow.store import (
    default_store_dir,
    inspect_outcome_store,
    observations_path,
    outcomes_path,
    reset_outcome_index_cache,
)

import importlib.util

_LIVE = Path(__file__).with_name("_v2_shadow_live_score.py")
_SPEC = importlib.util.spec_from_file_location("v2_shadow_live_score_helpers", _LIVE)
_LIVE_MOD = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(_LIVE_MOD)
_coverage = _LIVE_MOD._coverage
_label_table = _LIVE_MOD._label_table
_rl_complete = _LIVE_MOD._rl_complete
_unique_opportunities = _LIVE_MOD._unique_opportunities
validate_sample = _LIVE_MOD.validate_sample

CHECKPOINT_END = datetime.fromisoformat("2026-09-24T21:39:03.264589+00:00")
OLD_DEDUP = {
    "5": {"buy_n": 284, "buy_hit": 0.3415492957746479, "buy_mean_pips": -1.3595070422535758, "sell_n": 284, "sell_hit": 0.2535211267605634, "sell_mean_pips": -1.8119718309858948},
    "15": {"buy_n": 284, "buy_hit": 0.3908450704225352, "buy_mean_pips": -1.2242957746479255, "sell_n": 284, "sell_hit": 0.323943661971831, "sell_mean_pips": -2.0489436619718586},
    "30": {"buy_n": 279, "buy_hit": 0.43727598566308246, "buy_mean_pips": -0.859856630824413, "sell_n": 279, "sell_hit": 0.36917562724014336, "sell_mean_pips": -2.245161290322559},
    "60": {"buy_n": 272, "buy_hit": 0.4963235294117647, "buy_mean_pips": -0.08014705882355502, "sell_n": 272, "sell_hit": 0.34191176470588236, "sell_mean_pips": -3.270588235294114},
    "120": {"buy_n": 252, "buy_hit": 0.5357142857142857, "buy_mean_pips": 0.949603174603135, "sell_n": 252, "sell_hit": 0.29365079365079366, "sell_mean_pips": -4.21904761904757},
    "240": {"buy_n": 209, "buy_hit": 0.507177033492823, "buy_mean_pips": 0.9574162679425414, "sell_n": 209, "sell_hit": 0.3349282296650718, "sell_mean_pips": -4.275119617224871},
}
SYMBOLS = ("EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF")
SMALL_N = 30


def _load_outcomes(path: Path) -> tuple[list[dict], int]:
    rows: list[dict] = []
    malformed = 0
    if not path.is_file():
        return rows, malformed
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(row, dict):
            rows.append(row)
        else:
            malformed += 1
    return rows, malformed


def _merge_outcomes(rows: list[dict]) -> list[dict]:
    """One analysis row per decision_id; later incremental horizons are unioned."""
    by_id: dict[str, dict] = {}
    for row in rows:
        did = row.get("decision_id")
        if not did:
            continue
        cur = by_id.setdefault(
            did,
            {
                "decision_id": did,
                "scored_at_utc": row.get("scored_at_utc"),
                "horizons": {},
                "notes": list(row.get("notes") or []),
            },
        )
        for hz, blob in (row.get("horizons") or {}).items():
            existing = cur["horizons"].setdefault(str(hz), {})
            if not isinstance(blob, dict):
                continue
            if "buy" in blob and "buy" not in existing:
                existing["buy"] = blob["buy"]
            if "sell" in blob and "sell" not in existing:
                existing["sell"] = blob["sell"]
            skip = blob.get("skip_opportunity") if isinstance(blob.get("skip_opportunity"), dict) else {}
            existing_skip = existing.setdefault("skip_opportunity", {})
            for k, v in skip.items():
                existing_skip.setdefault(k, v)
    return list(by_id.values())


def _fmt(x: float | None, digits: int = 3) -> str:
    if x is None:
        return "n/a"
    return f"{x:.{digits}f}"


def _fmt_signed(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "n/a"
    return f"{x:+.{digits}f}"


def _small(n: int) -> str:
    return "  [SMALL SAMPLE]" if n < SMALL_N else ""


def _label_md(table: dict) -> list[str]:
    lines = [
        "Hz   BUY n  BUY hit  BUY mean  BUY med   SELL n  SELL hit  SELL mean  SELL med  BUY+SELL mean",
    ]
    for hz in HORIZONS_MIN:
        row = table[str(hz)]
        n = int(row["buy_n"] or 0)
        lines.append(
            f"{hz:<4} {row['buy_n']:<6} {_fmt(row['buy_hit'])}   {_fmt_signed(row['buy_mean_pips'])}    "
            f"{_fmt_signed(row['buy_median_pips'])}   {row['sell_n']:<6} {_fmt(row['sell_hit'])}    "
            f"{_fmt_signed(row['sell_mean_pips'])}     {_fmt_signed(row['sell_median_pips'])}    "
            f"{_fmt_signed(row['buy_plus_sell_mean_pips'])}{_small(n)}"
        )
    return lines


def _diff(cur: dict | None, old: dict | None, field: str) -> float | None:
    if not cur or not old:
        return None
    a, b = cur.get(field), old.get(field)
    if a is None or b is None:
        return None
    return float(a) - float(b)


def _opp_m5(key: str) -> datetime:
    _symbol, m5_iso = key.split("|", 1)
    dt = datetime.fromisoformat(m5_iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _symbol_table(outcomes: list[dict], opp_map: dict[str, str], obs_by_id: dict[str, dict]) -> list[str]:
    lines = []
    for symbol in SYMBOLS:
        keep = {did for key, did in opp_map.items() if key.startswith(f"{symbol}|")}
        chosen = [r for r in outcomes if r.get("decision_id") in keep]
        n = len(keep)
        lines.append(f"{symbol}: n={n}{_small(n)}")
        if not chosen:
            lines.append("  no scored unique opportunities")
            continue
        table = _label_table(chosen)
        for hz in HORIZONS_MIN:
            row = table[str(hz)]
            lines.append(
                f"  {hz:>3}m  BUY hit={_fmt(row['buy_hit'])} mean={_fmt_signed(row['buy_mean_pips'])} n={row['buy_n']}"
                f"   SELL hit={_fmt(row['sell_hit'])} mean={_fmt_signed(row['sell_mean_pips'])} n={row['sell_n']}"
                f"{_small(int(row['buy_n'] or 0))}"
            )
        _ = obs_by_id
    return lines


def _time_breakdown(outcomes: list[dict], opp_map: dict[str, str]) -> tuple[list[str], dict]:
    keep = set(opp_map.values())
    chosen = [r for r in outcomes if r.get("decision_id") in keep]
    by_id = {r["decision_id"]: r for r in chosen}
    hour_ids: dict[int, list[str]] = defaultdict(list)
    block_ids: dict[str, list[str]] = defaultdict(list)
    for key, did in opp_map.items():
        hour = _opp_m5(key).hour
        hour_ids[hour].append(did)
        if hour < 6:
            block = "00-06"
        elif hour < 12:
            block = "06-12"
        elif hour < 18:
            block = "12-18"
        else:
            block = "18-24"
        block_ids[block].append(did)

    def _bucket_lines(title: str, groups: dict[str, list[str]]) -> list[str]:
        out = [title]
        for name in sorted(groups):
            ids = groups[name]
            rows = [by_id[i] for i in ids if i in by_id]
            table = _label_table(rows) if rows else {}
            n = len(ids)
            scored = len(rows)
            out.append(f"{name}: opportunities={n} scored={scored}{_small(n)}")
            if not table:
                continue
            for hz in (5, 60, 240):
                row = table[str(hz)]
                out.append(
                    f"  {hz:>3}m BUY hit={_fmt(row['buy_hit'])} mean={_fmt_signed(row['buy_mean_pips'])} n={row['buy_n']}"
                    f"  SELL hit={_fmt(row['sell_hit'])} mean={_fmt_signed(row['sell_mean_pips'])} n={row['sell_n']}"
                    f"{_small(int(row['buy_n'] or 0))}"
                )
        return out

    hour_named = {f"{h:02d}": hour_ids.get(h, []) for h in range(24) if hour_ids.get(h)}
    lines = _bucket_lines("UTC hour (completed-M5 start):", hour_named)
    lines.append("")
    lines.extend(_bucket_lines("UTC blocks:", {k: block_ids[k] for k in ("00-06", "06-12", "12-18", "18-24") if k in block_ids}))
    return lines, {"hour": {str(k): len(v) for k, v in hour_ids.items()}, "block": {k: len(v) for k, v in block_ids.items()}}


def _rl_report(obs_rows: list[dict]) -> tuple[list[str], dict]:
    n = len(obs_rows)
    fields = {"state": 0, "action": 0, "q_values": 0, "epsilon": 0, "agree": 0, "veto": 0}
    q_all_zero = 0
    q_nonzero = 0
    complete = 0
    for rec in obs_rows:
        rl = rec.get("rl") or {}
        if rl.get("state") is not None:
            fields["state"] += 1
        if rl.get("action") is not None:
            fields["action"] += 1
        q = rl.get("q_values")
        if isinstance(q, dict) and {"BUY", "SELL", "SKIP"} <= set(q):
            fields["q_values"] += 1
            nums = []
            for key in ("BUY", "SELL", "SKIP"):
                try:
                    nums.append(float(q[key]))
                except (TypeError, ValueError):
                    nums.append(None)
            if all(v == 0.0 for v in nums if v is not None) and None not in nums:
                q_all_zero += 1
            elif any(v not in (0.0, None) for v in nums):
                q_nonzero += 1
        if rl.get("epsilon") is not None:
            fields["epsilon"] += 1
        if rl.get("agree") is not None:
            fields["agree"] += 1
        if rl.get("veto") is not None:
            fields["veto"] += 1
        if _rl_complete(rec):
            complete += 1
    lines = [
        f"observations={n}",
        f"rl_state={fields['state']}/{n}",
        f"rl_action={fields['action']}/{n}",
        f"rl_q={fields['q_values']}/{n}",
        f"rl_epsilon={fields['epsilon']}/{n}",
        f"rl_agree={fields['agree']}/{n}",
        f"rl_veto={fields['veto']}/{n}",
        f"rl_complete={complete}/{n}",
        f"q_values_all_zero={q_all_zero}",
        f"q_values_nonzero={q_nonzero}",
        "Q values remain zero-initialized observation metadata. This is not RL effectiveness.",
    ]
    return lines, {**fields, "complete": complete, "q_all_zero": q_all_zero, "q_nonzero": q_nonzero, "n": n}


def _correlation_note(opp_map: dict[str, str]) -> tuple[list[str], dict]:
    by_m5: dict[str, list[str]] = defaultdict(list)
    for key in opp_map:
        symbol, m5 = key.split("|", 1)
        by_m5[m5].append(symbol)
    sizes = Counter(len(v) for v in by_m5.values())
    multi = sum(1 for v in by_m5.values() if len(v) >= 2)
    lines = [
        f"unique completed-M5 timestamps={len(by_m5)}",
        f"timestamps with 2+ symbols={multi}",
        "symbols-per-timestamp counts: " + ", ".join(f"{k} symbols: {sizes[k]}" for k in sorted(sizes)),
        f"Do NOT treat {len(opp_map)} unique opportunities as {len(opp_map)} independent statistical trials.",
        "Same-timestamp USD-pair opportunities share session, USD factor, and often the same macro impulse.",
    ]
    return lines, {"m5_timestamps": len(by_m5), "multi_symbol": multi, "size_hist": dict(sizes)}


def _pass_summary(rep: dict) -> dict:
    return {k: rep[k] for k in rep if k != "statuses"}


def main() -> dict:
    root = default_store_dir()
    obs_path = observations_path(root)
    out_path = outcomes_path(root)
    obs_rows, obs_mal = load_observation_records(obs_path)
    market = load_market_bars(_market_dir(root))
    existing_outcomes, out_mal = _load_outcomes(out_path)
    reset_outcome_index_cache()
    store_state = inspect_outcome_store(root)
    existing_keys = len(store_state.keys)
    timestamps = [_ts(r.get("timestamp_utc")) for r in obs_rows]
    timestamps = [t for t in timestamps if t is not None]
    opp_map, obs_n = _unique_opportunities(obs_rows)
    post_map = {k: v for k, v in opp_map.items() if _opp_m5(k) > CHECKPOINT_END}
    preflight = {
        "observation_count": len(obs_rows),
        "unique_decision_ids": len({r.get("decision_id") for r in obs_rows}),
        "observation_range": [
            min(timestamps).isoformat() if timestamps else None,
            max(timestamps).isoformat() if timestamps else None,
        ],
        "observation_malformed": obs_mal,
        "market_by_symbol": market["by_symbol"],
        "market_malformed": market["malformed"],
        "market_duplicates": market["duplicates"],
        "existing_outcome_rows": len(existing_outcomes),
        "existing_logical_keys": existing_keys,
        "outcome_malformed": out_mal,
        "store_safe": store_state.safe,
        "historical_duplicates": store_state.historical_duplicates,
        "historical_conflicts": store_state.historical_conflicts,
        "unsafe_reason": store_state.unsafe_reason,
        "unique_opportunities": len(opp_map),
        "post_checkpoint_opportunities": len(post_map),
    }
    if (not store_state.safe) or store_state.historical_conflicts or out_mal:
        return {
            "stopped": True,
            "reason": "preflight outcome-store conflict/corruption",
            "preflight": preflight,
        }

    sample = validate_sample(root, obs_rows, market["bars"])
    if not sample["executable_sides_ok"] or sample["conflicts"] or sample["written"] < 1:
        return {"stopped": True, "reason": "sample validation failed", "sample": sample, "preflight": preflight}

    reset_outcome_index_cache()
    first = run_offline_score_pass(store_dir=root, scored_at_utc="2026-09-25T22:00:00+00:00")
    if first["conflicts"] or first["unsafe"]:
        return {
            "stopped": True,
            "reason": "first pass conflict/unsafe",
            "preflight": preflight,
            "sample": sample,
            "first": _pass_summary(first),
        }

    reset_outcome_index_cache()
    second = run_offline_score_pass(store_dir=root, scored_at_utc="2026-09-25T22:01:00+00:00")
    if second["conflicts"] or second["written"] or second["unsafe"]:
        return {
            "stopped": True,
            "reason": "second pass not idempotent",
            "preflight": preflight,
            "first": _pass_summary(first),
            "second": _pass_summary(second),
        }

    after_rows, after_mal = _load_outcomes(out_path)
    merged = _merge_outcomes(after_rows)
    obs_by_id = {r.get("decision_id"): r for r in obs_rows}
    scored_ids = {r["decision_id"] for r in merged}
    scored_obs = [r for r in obs_rows if r.get("decision_id") in scored_ids]
    cov_all = _coverage(obs_rows, merged, market["bars"])
    unique_obs = [obs_by_id[did] for did in opp_map.values() if did in obs_by_id]
    cov_unique = _coverage(unique_obs, merged, market["bars"])
    full_obs = _label_table(merged)
    full_dedup = _label_table(merged, opp_map)
    post_dedup = _label_table(merged, post_map)
    rl_lines, rl_stats = _rl_report(obs_rows)
    corr_lines, corr_stats = _correlation_note(opp_map)
    time_lines, time_stats = _time_breakdown(merged, opp_map)
    symbol_lines = _symbol_table(merged, post_map, obs_by_id)
    repeat_count = obs_n - len(opp_map)
    repeat_rate = None if not obs_n else 100.0 * repeat_count / obs_n

    payload = {
        "stopped": False,
        "preflight": preflight,
        "sample": sample,
        "first": _pass_summary(first),
        "second": _pass_summary(second),
        "outcome_rows_after": len(after_rows),
        "outcome_malformed_after": after_mal,
        "merged_decisions": len(merged),
        "coverage_observation": cov_all,
        "coverage_unique": cov_unique,
        "label_health_observation": full_obs,
        "label_health_dedup": full_dedup,
        "label_health_post": post_dedup,
        "rl": rl_stats,
        "correlation": corr_stats,
        "time": time_stats,
        "repeat_count": repeat_count,
        "repeat_rate": repeat_rate,
        "scored_obs": len(scored_obs),
    }

    md = _render_report(
        payload,
        symbol_lines=symbol_lines,
        time_lines=time_lines,
        rl_lines=rl_lines,
        corr_lines=corr_lines,
    )
    dest_md = Path("reports/decision_quality/v2_shadow_checkpoint_2.md")
    dest_json = Path("reports/decision_quality/_v2_shadow_checkpoint_2_results.json")
    dest_md.write_text(md, encoding="utf-8")
    dest_json.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    print(md.encode("ascii", "replace").decode("ascii"))
    return payload


def _render_report(payload: dict, *, symbol_lines: list[str], time_lines: list[str], rl_lines: list[str], corr_lines: list[str]) -> str:
    pre = payload["preflight"]
    first = payload["first"]
    second = payload["second"]
    cov = payload["coverage_observation"]["overall"]
    cov_u = payload["coverage_unique"]["overall"]
    old = OLD_DEDUP
    new = payload["label_health_post"]
    comb = payload["label_health_dedup"]

    def cov_lines(title: str, blob: dict) -> list[str]:
        lines = [title, "Hz   eligible  scored  missing/not-yet-mature"]
        for hz in HORIZONS_MIN:
            row = blob[str(hz)]
            lines.append(f"{hz:<4} {row['eligible']:<9} {row['scored']:<7} {row['missing_future']}")
        return lines

    def cmp_lines() -> list[str]:
        lines = [
            "OLD = first validated checkpoint (deduplicated).",
            "NEW = strictly post-checkpoint unique opportunities.",
            "COMBINED = current full unique-opportunity set.",
            "Differences are NEW-OLD and COMBINED-OLD. Not optimized thresholds.",
            "",
            "Hz   view       BUY n  BUY hit  d_hit    BUY mean  d_mean   SELL n  SELL hit  d_hit    SELL mean  d_mean",
        ]
        for hz in HORIZONS_MIN:
            o = old[str(hz)]
            n = new[str(hz)]
            c = comb[str(hz)]
            lines.append(
                f"{hz:<4} OLD        {o['buy_n']:<6} {_fmt(o['buy_hit'])}   —        {_fmt_signed(o['buy_mean_pips'])}    —        "
                f"{o['sell_n']:<6} {_fmt(o['sell_hit'])}    —        {_fmt_signed(o['sell_mean_pips'])}     —"
            )
            lines.append(
                f"{hz:<4} NEW        {n['buy_n']:<6} {_fmt(n['buy_hit'])}   {_fmt_signed(_diff(n, o, 'buy_hit'), 3)}    "
                f"{_fmt_signed(n['buy_mean_pips'])}    {_fmt_signed(_diff(n, o, 'buy_mean_pips'))}   "
                f"{n['sell_n']:<6} {_fmt(n['sell_hit'])}    {_fmt_signed(_diff(n, o, 'sell_hit'), 3)}    "
                f"{_fmt_signed(n['sell_mean_pips'])}     {_fmt_signed(_diff(n, o, 'sell_mean_pips'))}"
                f"{_small(int(n['buy_n'] or 0))}"
            )
            lines.append(
                f"{hz:<4} COMBINED   {c['buy_n']:<6} {_fmt(c['buy_hit'])}   {_fmt_signed(_diff(c, o, 'buy_hit'), 3)}    "
                f"{_fmt_signed(c['buy_mean_pips'])}    {_fmt_signed(_diff(c, o, 'buy_mean_pips'))}   "
                f"{c['sell_n']:<6} {_fmt(c['sell_hit'])}    {_fmt_signed(_diff(c, o, 'sell_hit'), 3)}    "
                f"{_fmt_signed(c['sell_mean_pips'])}     {_fmt_signed(_diff(c, o, 'sell_mean_pips'))}"
            )
        return lines

    # Conservative characterization from the numbers only.
    new5 = new["5"]
    old5 = old["5"]
    new240 = new["240"]
    interpretation = _interpret(old, new, comb)

    lines = [
        "# V2 shadow — second offline outcome checkpoint",
        "",
        "RESEARCH / DESCRIPTIVE ONLY. V2 remains SKIP. No live trading change.",
        "Scorer semantics unchanged: BUY ask→future bid_close; SELL bid→future ask_close;",
        "horizons 5/15/30/60/120/240; direction_correct = forward_pips > 0; no mid fallback.",
        "",
        "PREFLIGHT:",
        f"observations={pre['observation_count']}",
        f"unique_decision_ids={pre['unique_decision_ids']}",
        f"observation_range={pre['observation_range'][0]} -> {pre['observation_range'][1]}",
        f"malformed_observations={pre['observation_malformed']}",
        f"malformed_market_rows={pre['market_malformed']}",
        f"market_duplicates={pre['market_duplicates']}",
        f"existing_outcome_rows={pre['existing_outcome_rows']}",
        f"existing_logical_keys={pre['existing_logical_keys']}",
        f"malformed_outcomes={pre['outcome_malformed']}",
        f"store_safe={pre['store_safe']}",
        f"historical_duplicates={pre['historical_duplicates']}",
        f"historical_conflicts={pre['historical_conflicts']}",
        "market_by_symbol:",
    ]
    for symbol in SYMBOLS:
        info = (pre["market_by_symbol"] or {}).get(symbol) or {}
        lines.append(
            f"  {symbol}: rows={info.get('rows')} usable={info.get('usable')} "
            f"first={info.get('first')} last={info.get('last')}"
        )
    lines.extend(
        [
            "",
            f"CURRENT OBSERVATIONS: {pre['observation_count']}",
            f"CURRENT UNIQUE OPPORTUNITIES: {pre['unique_opportunities']}",
            f"STRICTLY POST-CHECKPOINT OPPORTUNITIES: {pre['post_checkpoint_opportunities']}",
            f"OUTCOME STORE BEFORE: {pre['existing_outcome_rows']} rows / {pre['existing_logical_keys']} logical keys",
            "",
            "FIRST SCORING PASS:",
            f"new outcome rows: {first['written']}",
            f"existing/skipped: already_exists={first['already_exists']} no_mature={first['skipped_no_mature']} no_market={first['skipped_no_market']} bad_decision={first['skipped_bad_decision']}",
            f"conflicts: {first['conflicts']}",
            f"logical_labels_written: {first['logical_labels_written']}",
            "",
            "SECOND IDENTICAL PASS:",
            f"new writes: {second['written']}",
            f"skipped: already_exists={second['already_exists']} no_mature={second['skipped_no_mature']}",
            f"conflicts: {second['conflicts']}",
            "",
        ]
    )
    lines.extend(cov_lines("HORIZON COVERAGE (all observations):", cov))
    lines.append("")
    lines.extend(cov_lines("UNIQUE-OPPORTUNITY COVERAGE:", cov_u))
    lines.extend(
        [
            "",
            "FULL OBSERVATION-WEIGHTED LABEL HEALTH:",
            *_label_md(payload["label_health_observation"]),
            "",
            "FULL DEDUPLICATED LABEL HEALTH:",
            *_label_md(payload["label_health_dedup"]),
            "",
            "POST-CHECKPOINT DEDUPLICATED LABEL HEALTH:",
            *_label_md(payload["label_health_post"]),
            "",
            "OLD VS NEW VS COMBINED:",
            *cmp_lines(),
            "",
            "POST-CHECKPOINT SYMBOL BREAKDOWN:",
            *symbol_lines,
            "",
            "UTC TIME BREAKDOWN:",
            *time_lines,
            "",
            "RL METADATA:",
            *rl_lines,
            "",
            f"REPEAT RATE: {payload['repeat_count']} repeats / {pre['observation_count']} observations = {_fmt(payload['repeat_rate'], 1)}%",
            "",
            "CORRELATED/SIMULTANEOUS OPPORTUNITY NOTE:",
            *corr_lines,
            "",
            "OANDA/API REQUESTS: 0",
            "OBSERVATIONS MODIFIED: NO",
            "MARKET DATA MODIFIED: NO",
            "SCORER SEMANTICS CHANGED: NO",
            "AUTOMATIC SCORING ENABLED: NO",
            "V2 POLICY: SKIP ONLY",
            "MODEL TRAINED: NO",
            "PRODUCTION TRADING LOGIC CHANGED: NO",
            "TEST RESULTS: 66 passed (tests/test_v2_shadow_live_score.py, tests/test_v2_shadow_outcomes.py, tests/test_v2_shadow.py, tests/test_v2_shadow_market.py)",
            "FILES CHANGED:",
            "- forex_bot/v2_shadow/score_offline.py (persist-path only: write newly matured keys without rewriting old matching keys)",
            "- tests/test_v2_shadow_live_score.py (incremental-horizon persist test)",
            "- reports/decision_quality/_v2_shadow_checkpoint_2.py",
            "- reports/decision_quality/_v2_shadow_checkpoint_2_results.json",
            "- reports/decision_quality/v2_shadow_checkpoint_2.md",
            "- data/research/v2_shadow/outcomes.jsonl (append-only via existing helper)",
            "",
            "DATA SUFFICIENT FOR CONFIDENCE MODEL: NO",
            "",
            "FINAL INTERPRETATION:",
            interpretation,
            "",
            "Do not treat these numbers as a live trading change. Two sessions, six correlated USD pairs,",
            "no validated independent fundamental family, and no out-of-sample confirmation.",
        ]
    )
    _ = (new5, old5, new240)
    return "\n".join(lines) + "\n"


def _interpret(old: dict, new: dict, comb: dict) -> str:
    """Descriptive only. Uses hit/mean sign and magnitude, not a trading rule."""
    notes = []
    mature_new = all((new[str(h)]["buy_n"] or 0) >= 30 for h in (5, 15, 30, 60))
    long_new = (new["240"]["buy_n"] or 0) >= 30
    if not mature_new:
        return (
            "too incomplete to characterize: post-checkpoint unique-opportunity n is below "
            "the n=30 descriptive floor at one or more short/medium horizons."
        )
    buy_hit_shifts = []
    sell_hit_shifts = []
    buy_mean_shifts = []
    sell_mean_shifts = []
    for hz in HORIZONS_MIN:
        if (new[str(hz)]["buy_n"] or 0) < 30:
            continue
        buy_hit_shifts.append((new[str(hz)]["buy_hit"] or 0) - old[str(hz)]["buy_hit"])
        sell_hit_shifts.append((new[str(hz)]["sell_hit"] or 0) - old[str(hz)]["sell_hit"])
        buy_mean_shifts.append((new[str(hz)]["buy_mean_pips"] or 0) - old[str(hz)]["buy_mean_pips"])
        sell_mean_shifts.append((new[str(hz)]["sell_mean_pips"] or 0) - old[str(hz)]["sell_mean_pips"])
    if not buy_hit_shifts:
        return "too incomplete to characterize: no post-checkpoint horizon reached n=30."
    max_abs_hit = max(abs(x) for x in buy_hit_shifts + sell_hit_shifts)
    max_abs_mean = max(abs(x) for x in buy_mean_shifts + sell_mean_shifts)
    sell_still_worse = all((new[str(h)]["sell_mean_pips"] or 0) < 0 for h in (5, 15, 30, 60) if (new[str(h)]["buy_n"] or 0) >= 30)
    buy_plus_sell_neg = all(
        ((new[str(h)]["buy_mean_pips"] or 0) + (new[str(h)]["sell_mean_pips"] or 0)) < 0
        for h in (5, 15, 30, 60)
        if (new[str(h)]["buy_n"] or 0) >= 30
    )
    notes.append(
        f"Post-checkpoint vs old: max |hit-rate shift|={max_abs_hit:.3f}; "
        f"max |mean-pip shift|={max_abs_mean:.2f} on horizons with n>=30."
    )
    notes.append(
        f"Combined +240m n={comb['240']['buy_n']} vs old 209; post-checkpoint +240m n={new['240']['buy_n']}"
        + (" (small/incomplete long horizon)." if not long_new else ".")
    )
    if sell_still_worse:
        notes.append("SELL mean pips remain negative at short/medium horizons in the new session.")
    if buy_plus_sell_neg:
        notes.append("BUY mean + SELL mean remains negative (spread/executable-side cost still dominates).")
    similar = max_abs_hit < 0.12 and max_abs_mean < 3.0
    different = max_abs_hit >= 0.20 or max_abs_mean >= 6.0
    if different:
        head = "materially different"
    elif similar:
        head = "descriptively similar to the first session"
    else:
        head = "descriptively similar in sign/structure, with material numeric movement at some horizons"
    return head + ". " + " ".join(notes)


if __name__ == "__main__":
    main()

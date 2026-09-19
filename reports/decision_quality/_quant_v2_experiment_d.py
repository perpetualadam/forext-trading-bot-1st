"""Quant V2 Experiment D: official scheduled-event proximity. Research-only."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from forex_bot.decision_quality.cross_pair import RETURN_BARS, cross_section_std, instrument_to_usd, synchronized_panel
from forex_bot.decision_quality.event_discovery import assign_split, future_path_block
from forex_bot.decision_quality.feature_discovery import SYMBOLS, utc_now
from forex_bot.decision_quality.history_cache import default_historical_dir
from forex_bot.decision_quality.schedule import (
    ACTIVITY_EDGES,
    CATEGORIES,
    CURRENCIES,
    DISP_EDGES,
    HORIZONS_MIN,
    NORM_DIR,
    NORMALIZATION_VERSION,
    PAIR_MAP,
    PERIOD_END,
    PERIOD_START,
    POST_WINDOWS,
    PRE_WINDOWS,
    RAW_DIR,
    activity_quintile,
    analysis_fields_clean,
    as_naive_utc,
    assign_post_window,
    assign_pre_window,
    checksum_file,
    clock_key,
    dispersion_quintile,
    event_bootstrap_diff,
    exclude_uncertain,
    find_duplicates,
    first_eligible_post_m5_start,
    is_primary_period,
    last_eligible_pre_m5_end,
    local_clock_to_utc,
    merge_official_rows,
    minutes_to_event,
    parse_bls_ref_release_table,
    parse_bls_year_lines,
    parse_boe_date_page,
    parse_boc_html,
    parse_fomc_meeting_blocks,
    parse_ons_version_clocks,
    parse_statcan_named_dates,
    sha256_bytes,
)
from forex_bot.decision_quality.sessions import classify_session
from forex_bot.decision_quality.spread_volume import apply_frozen_edges, half_close_spread
from forex_bot.indicators import _true_range
from forex_bot.profit_protection import pip_size

OUT = Path("reports/decision_quality/quant_v2_experiment_d_data.json")
PROGRESS = Path("reports/decision_quality/quant_v2_experiment_d_progress.json")
REPORT = Path("reports/decision_quality/quant_v2_experiment_d_schedule_proximity.md")
EVENTS_PATH = NORM_DIR / f"official_schedule_events_{NORMALIZATION_VERSION}.json"
HIST = default_historical_dir()
H = 60  # primary horizon minutes


def _j(obj):
    if isinstance(obj, dict):
        return {str(k): _j(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_j(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if not np.isfinite(obj) else float(obj)
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, pd.Timestamp):
        return str(obj)
    return str(obj)


def dump(progress, results):
    PROGRESS.write_text(json.dumps(_j(progress), indent=2), encoding="utf-8")
    OUT.write_text(json.dumps(_j(results), indent=2), encoding="utf-8")


def mark(progress, n, name, t0, findings):
    progress["stages"].append(
        {
            "stage": n,
            "stage_name": name,
            "status": "completed",
            "started_at_utc": t0,
            "finished_at_utc": utc_now(),
            "findings": findings,
        }
    )
    progress["completed_stages"] = sorted({s["stage"] for s in progress["stages"]})
    progress["current_stage"] = n
    progress["last_checkpoint_at_utc"] = utc_now()


def _read(agency: str, name: str) -> str:
    matches = list((RAW_DIR / agency).rglob(name))
    if not matches:
        return ""
    return matches[0].read_text(encoding="utf-8", errors="replace")


def collect_official_events() -> list[dict]:
    groups = []
    groups.append(parse_bls_year_lines(_read("BLS", "year_2025_cpi_empsit.txt")))
    groups.append(parse_bls_ref_release_table(_read("BLS", "empsit_schedule_table.txt"), "EMPLOYMENT"))
    groups.append(parse_bls_ref_release_table(_read("BLS", "cpi_schedule_table.htm"), "INFLATION"))
    groups.append(parse_fomc_meeting_blocks(_read("FRB", "fomccalendars.htm")))
    groups.append(parse_boe_date_page(_read("BOE", "mpc_dates_2025.htm")))
    groups.append(parse_boe_date_page(_read("BOE", "mpc_dates_2026.htm")))
    groups.append(parse_boe_date_page(_read("BOE", "upcoming_mpc_dates.htm")))
    groups.append(parse_ons_version_clocks(_read("ONS", "cpi_dataset_current.htm"), "INFLATION"))
    groups.append(parse_ons_version_clocks(_read("ONS", "lms_dataset_current.htm"), "EMPLOYMENT"))
    groups.append(parse_boc_html(_read("BOC", "schedule_2025.htm")))
    groups.append(parse_boc_html(_read("BOC", "schedule_2026.htm")))
    groups.append(parse_statcan_named_dates(_read("STATCAN", "release_2026.txt"), "INFLATION"))
    groups.append(parse_statcan_named_dates(_read("STATCAN", "release_2026.txt"), "EMPLOYMENT"))
    groups.append(parse_statcan_named_dates(_read("STATCAN", "the_daily_2025_schedule.txt"), "INFLATION"))
    groups.append(parse_statcan_named_dates(_read("STATCAN", "the_daily_2025_schedule.txt"), "EMPLOYMENT"))
    rows = merge_official_rows(*groups)
    for r in rows:
        assert analysis_fields_clean(r)
        r["in_primary_period"] = bool(r.get("scheduled_ts_utc") and is_primary_period(datetime.fromisoformat(r["scheduled_ts_utc"])))
    return rows


def load_symbol(symbol: str) -> pd.DataFrame:
    raw = pd.read_csv(HIST / f"{symbol}_M5.csv")
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    raw["time"] = pd.to_datetime(raw["time"], utc=True).dt.tz_localize(None)
    raw["symbol"] = symbol
    pip = pip_size(symbol)
    close = raw["close"].astype(float)
    atr = _true_range(raw["high"], raw["low"], close).rolling(14).mean()
    raw["atr14"] = atr
    raw["half_spread_pips"] = half_close_spread(raw["ask_close"], raw["bid_close"]) / pip
    raw["volume"] = pd.to_numeric(raw["volume"], errors="coerce")
    raw["session"] = [classify_session(x.to_pydatetime()) for x in raw["time"]]
    raw["split"] = assign_split(raw["time"])
    raw["weekday"] = raw["time"].dt.weekday
    raw["utc_hour"] = raw["time"].dt.hour
    raw["bar_end"] = raw["time"] + pd.Timedelta(minutes=5)
    for b in RETURN_BARS:
        raw[f"usd_ret_{b}"] = instrument_to_usd(symbol, close.pct_change(b).to_numpy())
    c = close.to_numpy(dtype=float)
    h = raw["high"].to_numpy(dtype=float)
    lo = raw["low"].to_numpy(dtype=float)
    for hz in HORIZONS_MIN:
        blk = future_path_block(c, h, lo, hz // 5)
        raw[f"abs_close_{hz}m"] = np.abs(blk["fwd_close"] - c) / pip
        raw[f"mfe_up_{hz}m"] = (blk["fwd_high"] - c) / pip
        raw[f"mfe_dn_{hz}m"] = (c - blk["fwd_low"]) / pip
        raw[f"mae_{hz}m"] = np.maximum(raw[f"mfe_up_{hz}m"], raw[f"mfe_dn_{hz}m"])
        raw[f"range_{hz}m"] = (blk["fwd_high"] - blk["fwd_low"]) / pip
        raw[f"signed_{hz}m"] = (blk["fwd_close"] - c) / pip
        raw[f"abs_atr_{hz}m"] = np.abs(blk["fwd_close"] - c) / (atr.to_numpy() + 1e-12)
        raw[f"abs_cost_{hz}m"] = np.abs(blk["fwd_close"] - c) / pip / (raw["half_spread_pips"].to_numpy() + 1e-12)
    return raw


def attach_activity_dispersion(frames: dict[str, pd.DataFrame]) -> None:
    all_df = pd.concat(frames.values(), ignore_index=True)
    tr = all_df["split"] == "train"
    med = all_df.loc[tr].groupby(["symbol", "session"], sort=False)["volume"].median()
    for sym, df in frames.items():
        key = list(zip(df["symbol"], df["session"]))
        df["train_sess_vol_med"] = [med.get((s, sess), np.nan) for s, sess in key]
        df["vol_sess_rel"] = df["volume"] / (df["train_sess_vol_med"] + 1e-12)
        df["q_vol_rel"] = apply_frozen_edges(df["vol_sess_rel"].to_numpy(), ACTIVITY_EDGES)
        assert np.allclose(df["q_vol_rel"].to_numpy(), activity_quintile(df["vol_sess_rel"].to_numpy()))
    wide = synchronized_panel({s: frames[s] for s in SYMBOLS}, "usd_ret_6")
    disp = cross_section_std(wide)
    disp_map = disp.to_dict()
    for df in frames.values():
        df["disp_std"] = df["time"].map(disp_map)
        df["q_disp"] = apply_frozen_edges(df["disp_std"].to_numpy(), DISP_EDGES)
        assert np.allclose(
            df["q_disp"].to_numpy()[np.isfinite(df["disp_std"])],
            dispersion_quintile(df["disp_std"].to_numpy())[np.isfinite(df["disp_std"])],
        )


def event_times(events: list[dict]) -> list[datetime]:
    return [datetime.fromisoformat(e["scheduled_ts_utc"]) for e in events if e.get("scheduled_ts_utc")]


def near_any(ts, clocks, pad_min=120) -> bool:
    for c in clocks:
        if abs((ts - c).total_seconds()) <= pad_min * 60:
            return True
    return False


def pick_window_bar(df: pd.DataFrame, scheduled: datetime, side: str, wid: str) -> pd.Series | None:
    if side == "pre":
        lo, hi = next((a, b) for w, a, b in PRE_WINDOWS if w == wid)
        mte = (pd.Timestamp(scheduled) - df["bar_end"]).dt.total_seconds() / 60.0
        mask = (mte > lo) & (mte <= hi)
        sub = df.loc[mask]
        if sub.empty:
            return None
        return sub.iloc[-1]
    lo, hi = next((a, b) for w, a, b in POST_WINDOWS if w == wid)
    first_start = pd.Timestamp(first_eligible_post_m5_start(scheduled))
    maa = (df["bar_end"] - pd.Timestamp(scheduled)).dt.total_seconds() / 60.0
    mask = (df["time"] >= first_start) & (maa >= lo) & (maa < hi)
    sub = df.loc[mask]
    if sub.empty:
        return None
    return sub.iloc[0]


def summarize_obs(obs: list[dict], key: str) -> dict:
    x = np.array([o[key] for o in obs if o.get(key) is not None and np.isfinite(o.get(key, np.nan))], dtype=float)
    if len(x) == 0:
        return {"n": 0}
    return {"n": int(len(x)), "mean": float(np.mean(x)), "median": float(np.median(x)), "p90": float(np.quantile(x, 0.90))}


def write_report(results: dict) -> None:
    v = results["verdict"]
    nxt = results["next_external"]
    lines = [
        "# Quant V2 Experiment D — Official scheduled-event proximity",
        "",
        f"**Status:** COMPLETE — research only. No model. No production change. Verdict: **{v['label']}**.",
        "",
        "Hypothesis A only: proximity to a pre-scheduled high-importance official economic event predicts future FX movement **magnitude**. Not a directional experiment. Incremental value is tested against frozen Experiment A OANDA activity and frozen Experiment B cross-sectional dispersion.",
        "",
        "## Acquisition",
        "",
        "Official schedule metadata only. Raw store: `data/research/external/raw/<agency>/<date>/`. Normalized: `data/research/external/normalized/`. Market M5/M1 CSVs were not modified.",
        "",
        "| Agency | Source identity | Clock convention |",
        "| --- | --- | --- |",
        "| BLS | `bls.gov/schedule/2025/`, CPI and Employment Situation release tables | 08:30 America/New_York |",
        "| FRB | `federalreserve.gov/monetarypolicy/fomccalendars.htm` | 14:00 America/New_York statement |",
        "| ONS | CPI and labour-market dataset previous-version clocks | 07:00 Europe/London |",
        "| BoE | Official MPC date pages 2025/2026 | 12:00 Europe/London |",
        "| StatCan | 2026-2027 release PDF + The Daily / major-release calendar | 08:30 America/New_York |",
        "| BoC | Official 2025 and 2026 rate-announcement schedule pages | **09:45 America/Toronto** (official page; not the earlier 10:00 placeholder) |",
        "",
        "Fields stored: event category, affected currency, official scheduled timestamp, timezone, UTC, source/ref, retrieval metadata. **No consensus, forecast, actual, revision, surprise, or text.**",
        "",
        f"Normalization version: `{NORMALIZATION_VERSION}`. BLS 2025 lapse-delayed clocks are `RESCHEDULED` and excluded from primary analysis. FOMC notation votes are `UNCERTAIN`.",
        "",
        "## Event inventory (primary period 2025-09-01 to 2026-08-31 UTC)",
        "",
    ]
    inv = results["inventory"]
    lines += [
        f"- Official rows parsed: {inv['n_parsed']}",
        f"- PRIMARY clock rows: {inv['n_primary_clock']}",
        f"- In development window: {inv['n_in_period']}",
        f"- RESCHEDULED / UNCERTAIN excluded from primary: {inv['n_excluded']}",
        f"- Median spacing of primary events: {inv['median_spacing_hours']} hours",
        f"- Simultaneous same-timestamp releases: {inv['n_simultaneous']}",
        f"- Overlapping ±120m windows: {inv['n_overlap_pairs']}",
        "",
        "### By currency / category (primary, in-period)",
        "",
        "| Currency | INFLATION | EMPLOYMENT | CENTRAL_BANK_DECISION | Total events |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for ccy in CURRENCIES:
        row = inv["by_currency_category"].get(ccy, {})
        tot = sum(int(row.get(k, 0)) for k in CATEGORIES)
        lines.append(
            f"| {ccy} | {row.get('INFLATION', 0)} | {row.get('EMPLOYMENT', 0)} | {row.get('CENTRAL_BANK_DECISION', 0)} | {tot} |"
        )
    lines += [
        "",
        "Independent n is **event count**, not surrounding M5 bars.",
        "",
        "## Frozen windows and clock control",
        "",
        "Pre: 120–60, 60–30, 30–15, 15–5 minutes before. Post: 0–15, 15–30, 30–60, 60–120 minutes after. Half-open as frozen. One observation per (event, window, symbol): last pre-window bar or first post-window bar. Base population: same symbol, UTC hour, weekday, outside any authorized event ±120 minutes.",
        "",
        "## Pre-event magnitude (60m abs close, pips) vs clock-matched base",
        "",
        "| Window | Category | Events | Event mean | Base mean | Diff | boot p05 | boot p95 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rec in results["pre_event"]:
        lines.append(
            f"| {rec['window']} | {rec['category']} | {rec['n_event']} | {_fmt(rec.get('event_mean'))} | {_fmt(rec.get('base_mean'))} | {_fmt(rec.get('diff'))} | {_fmt(rec.get('p05'))} | {_fmt(rec.get('p95'))} |"
        )
    lines += [
        "",
        "## Post-event magnitude (60m abs close, pips) vs clock-matched base",
        "",
        "| Window | Category | Events | Event mean | Base mean | Diff | boot p05 | boot p95 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rec in results["post_event"]:
        lines.append(
            f"| {rec['window']} | {rec['category']} | {rec['n_event']} | {_fmt(rec.get('event_mean'))} | {_fmt(rec.get('base_mean'))} | {_fmt(rec.get('diff'))} | {_fmt(rec.get('p05'))} | {_fmt(rec.get('p95'))} |"
        )
    lines += [
        "",
        "## Currency / symbol stability (post_0_15, 60m abs pips minus clock base)",
        "",
        "| Currency | Symbol | Events | Diff | boot p05 | boot p95 |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for rec in results["stability"]:
        lines.append(
            f"| {rec['currency']} | {rec['symbol']} | {rec['n_event']} | {_fmt(rec.get('diff'))} | {_fmt(rec.get('p05'))} | {_fmt(rec.get('p95'))} |"
        )
    lines += [
        "",
        f"Stability class: **{results['stability_class']}**.",
        "",
        "## Incremental value over frozen activity",
        "",
        "Question: at similar Experiment A session-relative volume quintiles, does official event proximity add magnitude?",
        "",
        "| Activity band | Window | Event mean | Matched-activity base | Diff | boot p05 | boot p95 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rec in results["vs_activity"]:
        lines.append(
            f"| {rec['band']} | {rec['window']} | {_fmt(rec.get('event_mean'))} | {_fmt(rec.get('base_mean'))} | {_fmt(rec.get('diff'))} | {_fmt(rec.get('p05'))} | {_fmt(rec.get('p95'))} |"
        )
    lines += [
        "",
        "## Incremental value over frozen dispersion",
        "",
        "| Dispersion band | Window | Event mean | Matched-dispersion base | Diff | boot p05 | boot p95 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rec in results["vs_dispersion"]:
        lines.append(
            f"| {rec['band']} | {rec['window']} | {_fmt(rec.get('event_mean'))} | {_fmt(rec.get('base_mean'))} | {_fmt(rec.get('diff'))} | {_fmt(rec.get('p05'))} | {_fmt(rec.get('p95'))} |"
        )
    lines += [
        "",
        "## Activity / dispersion / spread response",
        "",
        results["state_response_text"],
        "",
        "## Cost / tradeability",
        "",
        results["cost_text"],
        "",
        "## Time stability (development splits only)",
        "",
        "| Split | Window | Events | Diff |",
        "| --- | --- | ---: | ---: |",
    ]
    for rec in results["time_stability"]:
        lines.append(f"| {rec['split']} | {rec['window']} | {rec['n_event']} | {_fmt(rec.get('diff'))} |")
    lines += [
        "",
        "2025-09 through 2026-08 is already-inspected DEVELOPMENT / DISCOVERY. No pristine holdout claim.",
        "",
        "## Directional diagnostic (descriptive only)",
        "",
        results["directional_text"],
        "",
        "No directional hypothesis was authorized. Signed means are not a strategy.",
        "",
        "## Information classification",
        "",
        f"**{results['information_class']}**",
        "",
        "## Verdict answers",
        "",
    ]
    for i, (q, a) in enumerate(v["answers"].items(), 1):
        lines.append(f"{i}. {q} **{a}**")
    lines += [
        "",
        f"# {v['label']}",
        "",
        "D_PASS would not authorize training, BUY/SELL, or production changes. This run does not train and does not change `_quant_stub_vote`.",
        "",
        "## Next external-data decision",
        "",
        f"# {nxt['label']}",
        "",
        nxt["rationale"],
        "",
        "## Stop",
        "",
        "No consensus acquired. No actuals acquired. No purchase. No surprise study. No training. No event filters. No production change. No ATR/RL/bot restart. Stop after Experiment D.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def _fmt(x):
    if x is None:
        return "—"
    try:
        if not np.isfinite(x):
            return "—"
    except TypeError:
        return str(x)
    return f"{float(x):.3f}"


def main():
    progress = {
        "experiment": "quant_v2_experiment_d",
        "started_at_utc": utc_now(),
        "current_stage": 0,
        "completed_stages": [],
        "stages": [],
        "blocked": False,
    }
    results = {"frozen_spec": "reports/decision_quality/quant_v2_experiment_d_frozen_spec.json"}
    t0 = utc_now()

    events = collect_official_events()
    NORM_DIR.mkdir(parents=True, exist_ok=True)
    EVENTS_PATH.write_text(json.dumps(events, indent=2), encoding="utf-8")
    dups = find_duplicates(events)
    primary, excluded = exclude_uncertain(events)
    primary = [e for e in primary if e["row_status"] == "PRIMARY"]
    in_period = [e for e in primary if e.get("in_primary_period")]
    clocks = event_times(in_period)
    clocks.sort()
    spacing = np.array([(b - a).total_seconds() / 3600 for a, b in zip(clocks, clocks[1:])]) if len(clocks) > 1 else np.array([])
    sim = Counter(e["scheduled_ts_utc"] for e in in_period)
    n_sim = int(sum(v for v in sim.values() if v > 1))
    overlap = 0
    for i, a in enumerate(clocks):
        for b in clocks[i + 1 :]:
            if (b - a).total_seconds() <= 240 * 60:
                overlap += 1
            else:
                break
    by_cc = defaultdict(lambda: Counter())
    for e in in_period:
        by_cc[e["currency"]][e["category"]] += 1
    results["inventory"] = {
        "n_parsed": len(events),
        "n_primary_clock": len(primary),
        "n_in_period": len(in_period),
        "n_excluded": len(excluded) + sum(1 for e in events if e["row_status"] == "RESCHEDULED"),
        "n_duplicates_collapsed": len(dups),
        "median_spacing_hours": float(np.median(spacing)) if len(spacing) else None,
        "n_simultaneous": n_sim,
        "n_overlap_pairs": overlap,
        "by_currency_category": {c: dict(by_cc[c]) for c in CURRENCIES},
        "normalization_version": NORMALIZATION_VERSION,
        "raw_checksums": {
            p.as_posix(): checksum_file(p)
            for p in RAW_DIR.rglob("*")
            if p.is_file() and p.suffix in {".htm", ".txt", ".pdf", ".ics"}
        },
    }
    mark(progress, 3, "schedule_integrity", t0, {"n_in_period": len(in_period), "excluded": results["inventory"]["n_excluded"]})
    dump(progress, results)

    frames = {s: load_symbol(s) for s in SYMBOLS}
    attach_activity_dispersion(frames)
    m5_hash_after = {s: hashlib.sha256((HIST / f"{s}_M5.csv").read_bytes()).hexdigest() for s in SYMBOLS}
    results["m5_sha256_after_load"] = m5_hash_after

    # Build event-level observations
    obs = []
    for ev in in_period:
        scheduled = datetime.fromisoformat(ev["scheduled_ts_utc"])
        for sym in PAIR_MAP[ev["currency"]]:
            df = frames[sym]
            for wid, _, _ in PRE_WINDOWS:
                bar = pick_window_bar(df, scheduled, "pre", wid)
                if bar is None:
                    continue
                obs.append(_obs_row(ev, scheduled, sym, "pre", wid, bar))
            for wid, _, _ in POST_WINDOWS:
                bar = pick_window_bar(df, scheduled, "post", wid)
                if bar is None:
                    continue
                obs.append(_obs_row(ev, scheduled, sym, "post", wid, bar))
    results["n_event_window_symbol_rows"] = len(obs)

    # Clock-matched base per symbol/hour/weekday
    all_clocks = clocks
    base_by_key = {}
    for sym, df in frames.items():
        ends = [x.to_pydatetime() for x in df["bar_end"]]
        far = np.array([not near_any(t, all_clocks, 120) for t in ends])
        for (wd, hr), g in df.loc[far].groupby(["weekday", "utc_hour"], sort=False):
            base_by_key[(sym, int(wd), int(hr))] = g[f"abs_close_{H}m"].to_numpy(dtype=float)

    def event_vs_base(subset, extra_base_mask=None):
        # event-level: mean across symbols for that event
        by_ev = defaultdict(list)
        bases = []
        for o in subset:
            if o.get(f"abs_close_{H}m") is None or not np.isfinite(o[f"abs_close_{H}m"]):
                continue
            by_ev[o["event_id"]].append(o[f"abs_close_{H}m"])
            key = (o["symbol"], o["weekday"], o["utc_hour"])
            b = base_by_key.get(key)
            if b is not None and len(b):
                bases.append(float(np.nanmean(b)))
        ev_means = np.array([float(np.mean(v)) for v in by_ev.values()]) if by_ev else np.array([])
        boot = event_bootstrap_diff(ev_means, np.array(bases, dtype=float) if bases else np.array([np.nan]))
        return boot

    pre_tbl = []
    for wid, _, _ in PRE_WINDOWS:
        for cat in CATEGORIES + ("POOLED",):
            sub = [o for o in obs if o["side"] == "pre" and o["window"] == wid and (cat == "POOLED" or o["category"] == cat)]
            if cat != "POOLED" and not sub:
                continue
            boot = event_vs_base(sub)
            pre_tbl.append({"window": wid, "category": cat, **boot})
    post_tbl = []
    for wid, _, _ in POST_WINDOWS:
        for cat in CATEGORIES + ("POOLED",):
            sub = [o for o in obs if o["side"] == "post" and o["window"] == wid and (cat == "POOLED" or o["category"] == cat)]
            boot = event_vs_base(sub)
            post_tbl.append({"window": wid, "category": cat, **boot})
    results["pre_event"] = pre_tbl
    results["post_event"] = post_tbl

    stab = []
    signs = []
    for ev in in_period:
        diffs = []
        for rec in [
            r
            for r in [
                event_vs_base([o for o in obs if o["event_id"] == ev["event_id"] and o["window"] == "post_0_15" and o["symbol"] == s])
                for s in PAIR_MAP[ev["currency"]]
            ]
        ]:
            pass
    for ccy in CURRENCIES:
        for sym in PAIR_MAP[ccy]:
            sub = [o for o in obs if o["currency"] == ccy and o["symbol"] == sym and o["window"] == "post_0_15"]
            boot = event_vs_base(sub)
            stab.append({"currency": ccy, "symbol": sym, **boot})
            if boot.get("diff") is not None:
                signs.append(boot["diff"] > 0)
    if not signs:
        sclass = "NO INFORMATION"
    elif all(signs) and len(signs) >= 6:
        sclass = "BROAD"
    elif len({(r["currency"], r["diff"] is not None and r["diff"] > 0) for r in stab if r.get("diff") is not None}) <= 3:
        pos_cc = {r["currency"] for r in stab if r.get("diff") is not None and r["diff"] > 0}
        if len(pos_cc) == 1:
            sclass = "CURRENCY-SPECIFIC"
        elif any(r.get("p05") is not None and r["p05"] > 0 for r in stab) and not all(r.get("diff", 0) > 0 for r in stab if r.get("diff") is not None):
            sclass = "PAIR-SPECIFIC"
        else:
            sclass = "UNSTABLE"
    else:
        sclass = "UNSTABLE" if (0 < sum(signs) < len(signs)) else ("BROAD" if all(signs) else "NO INFORMATION")
    results["stability"] = stab
    results["stability_class"] = sclass

    def band_of(q):
        if q in (1, 2):
            return "low"
        if q == 3:
            return "mid"
        if q in (4, 5):
            return "high"
        return "na"

    vs_a = []
    vs_b = []
    for band, qs in (("low", {1, 2}), ("mid", {3}), ("high", {4, 5})):
        for wid in ("pre_15_5", "post_0_15"):
            sub = [o for o in obs if o["window"] == wid and o.get("q_vol_rel") in qs]
            # activity-matched base: clock base further restricted is heavy; use same-band ordinary bars
            bases = []
            evs = defaultdict(list)
            for o in sub:
                if not np.isfinite(o.get(f"abs_close_{H}m", np.nan)):
                    continue
                evs[o["event_id"]].append(o[f"abs_close_{H}m"])
            df = frames["EUR_USD"]  # placeholder unused
            for sym, f in frames.items():
                m = f["q_vol_rel"].isin(list(qs))
                ends = [x.to_pydatetime() for x in f.loc[m, "bar_end"]]
                keep = [not near_any(t, all_clocks, 120) for t in ends]
                vals = f.loc[m, f"abs_close_{H}m"].to_numpy(dtype=float)
                if keep:
                    bases.extend(vals[np.array(keep)])
            boot = event_bootstrap_diff(np.array([float(np.mean(v)) for v in evs.values()] or [np.nan]), np.asarray(bases, dtype=float))
            vs_a.append({"band": band, "window": wid, **boot})
            sub2 = [o for o in obs if o["window"] == wid and o.get("q_disp") in qs]
            evs2 = defaultdict(list)
            for o in sub2:
                if np.isfinite(o.get(f"abs_close_{H}m", np.nan)):
                    evs2[o["event_id"]].append(o[f"abs_close_{H}m"])
            bases2 = []
            for f in frames.values():
                m = f["q_disp"].isin(list(qs))
                ends = [x.to_pydatetime() for x in f.loc[m, "bar_end"]]
                keep = np.array([not near_any(t, all_clocks, 120) for t in ends])
                vals = f.loc[m, f"abs_close_{H}m"].to_numpy(dtype=float)
                if len(keep):
                    bases2.extend(vals[keep])
            boot2 = event_bootstrap_diff(np.array([float(np.mean(v)) for v in evs2.values()] or [np.nan]), np.asarray(bases2, dtype=float))
            vs_b.append({"band": band, "window": wid, **boot2})
    results["vs_activity"] = vs_a
    results["vs_dispersion"] = vs_b

    # State response: activity/dispersion/spread pre vs post
    def mean_field(window, field):
        xs = [o[field] for o in obs if o["window"] == window and o.get(field) is not None and np.isfinite(o[field])]
        return float(np.mean(xs)) if xs else None

    results["state_means"] = {
        "pre_15_5_vol": mean_field("pre_15_5", "vol_sess_rel"),
        "post_0_15_vol": mean_field("post_0_15", "vol_sess_rel"),
        "pre_15_5_disp": mean_field("pre_15_5", "disp_std"),
        "post_0_15_disp": mean_field("post_0_15", "disp_std"),
        "pre_15_5_spread": mean_field("pre_15_5", "half_spread_pips"),
        "post_0_15_spread": mean_field("post_0_15", "half_spread_pips"),
    }
    sm = results["state_means"]
    results["state_response_text"] = (
        f"Session-relative activity mean pre_15_5={_fmt(sm['pre_15_5_vol'])} vs post_0_15={_fmt(sm['post_0_15_vol'])}. "
        f"disp_std pre={_fmt(sm['pre_15_5_disp'])} vs post={_fmt(sm['post_0_15_disp'])}. "
        f"Half-spread pips pre={_fmt(sm['pre_15_5_spread'])} vs post={_fmt(sm['post_0_15_spread'])}."
    )

    # Cost: event vs clock base spreads and movement/cost
    ev_sp, base_sp, ev_mc, base_mc = [], [], [], []
    for o in obs:
        if o["window"] != "post_0_15":
            continue
        if np.isfinite(o.get("half_spread_pips", np.nan)):
            ev_sp.append(o["half_spread_pips"])
        if np.isfinite(o.get(f"abs_cost_{H}m", np.nan)):
            ev_mc.append(o[f"abs_cost_{H}m"])
        key = (o["symbol"], o["weekday"], o["utc_hour"])
        # reuse frames
    for sym, f in frames.items():
        ends = [x.to_pydatetime() for x in f["bar_end"]]
        keep = np.array([not near_any(t, all_clocks, 120) for t in ends])
        base_sp.extend(f.loc[keep, "half_spread_pips"].to_numpy(dtype=float))
        base_mc.extend(f.loc[keep, f"abs_cost_{H}m"].to_numpy(dtype=float))
    results["cost"] = {
        "event_post_spread_mean": float(np.nanmean(ev_sp)) if ev_sp else None,
        "base_spread_mean": float(np.nanmean(base_sp)) if len(base_sp) else None,
        "event_post_move_cost_mean": float(np.nanmean(ev_mc)) if ev_mc else None,
        "base_move_cost_mean": float(np.nanmean(base_mc)) if len(base_mc) else None,
        "event_spread_p90": float(np.nanquantile(ev_sp, 0.9)) if ev_sp else None,
        "base_spread_p90": float(np.nanquantile(base_sp, 0.9)) if len(base_sp) else None,
    }
    c = results["cost"]
    spread_worse = c["event_post_spread_mean"] is not None and c["base_spread_mean"] is not None and c["event_post_spread_mean"] > c["base_spread_mean"] * 1.1
    mc_better = c["event_post_move_cost_mean"] is not None and c["base_move_cost_mean"] is not None and c["event_post_move_cost_mean"] > c["base_move_cost_mean"] * 1.1
    results["cost_text"] = (
        f"Post-event half-spread mean {_fmt(c['event_post_spread_mean'])} pips vs clock-ordinary {_fmt(c['base_spread_mean'])} "
        f"(p90 {_fmt(c['event_spread_p90'])} vs {_fmt(c['base_spread_p90'])}). "
        f"60m |move|/half-spread {_fmt(c['event_post_move_cost_mean'])} vs {_fmt(c['base_move_cost_mean'])}. "
        "Higher movement/cost is not directional edge."
    )

    tstab = []
    for spl in ("train", "valid", "discovery_test"):
        for wid in ("pre_15_5", "post_0_15"):
            sub = [o for o in obs if o["window"] == wid and o["split"] == spl]
            boot = event_vs_base(sub)
            tstab.append({"split": spl, "window": wid, **boot})
    results["time_stability"] = tstab

    signed = [o[f"signed_{H}m"] for o in obs if o["window"] == "post_0_15" and np.isfinite(o.get(f"signed_{H}m", np.nan))]
    results["signed_post"] = {"n": len(signed), "mean": float(np.mean(signed)) if signed else None}
    results["directional_text"] = (
        f"Descriptive signed 60m instrument pips after scheduled time (post_0_15), n_rows={len(signed)}, "
        f"mean={_fmt(results['signed_post']['mean'])}. Incidental only."
    )

    # Classification / verdict from evidence
    post0 = next((r for r in post_tbl if r["window"] == "post_0_15" and r["category"] == "POOLED"), {})
    pre15 = next((r for r in pre_tbl if r["window"] == "pre_15_5" and r["category"] == "POOLED"), {})
    clock_survives = bool(post0.get("p05") is not None and post0["p05"] > 0)
    pre_survives = bool(pre15.get("p05") is not None and pre15["p05"] > 0)
    split_ok = all(
        (r.get("diff") or 0) > 0
        for r in tstab
        if r["window"] == "post_0_15" and r.get("n_event", 0) >= 3
    )
    pair_ok = sum(1 for r in stab if r.get("diff") is not None and r["diff"] > 0) >= max(3, len(stab) // 2)
    inc_a = any(r.get("p05") is not None and r["p05"] > 0 for r in vs_a if r["window"] == "post_0_15")
    inc_b = any(r.get("p05") is not None and r["p05"] > 0 for r in vs_b if r["window"] == "post_0_15")
    useful_where = "both" if clock_survives and pre_survives else ("post-event" if clock_survives else ("pre-event" if pre_survives else "neither"))

    if clock_survives and (inc_a or inc_b) and pair_ok:
        info = "INCREMENTAL MAGNITUDE INFORMATION"
        label = "D_PASS_INCREMENTAL_MAGNITUDE_INFORMATION"
    elif clock_survives and not inc_a and not inc_b:
        info = "REDUNDANT WITH ACTIVITY/DISPERSION"
        label = "D_REDUNDANT_CONTEXT"
    elif clock_survives or pre_survives:
        info = "WEAK / UNSTABLE CONTEXT"
        label = "D_NO_USEFUL_INFORMATION"
    else:
        info = "NO INFORMATION"
        label = "D_NO_USEFUL_INFORMATION"

    # If post effect exists but is redundant with activity AND dispersion
    if clock_survives and not inc_a and not inc_b:
        info = "REDUNDANT WITH ACTIVITY/DISPERSION"
        label = "D_REDUNDANT_CONTEXT"
    elif clock_survives and (inc_a or inc_b) and pair_ok:
        info = "INCREMENTAL MAGNITUDE INFORMATION"
        label = "D_PASS_INCREMENTAL_MAGNITUDE_INFORMATION"

    results["information_class"] = info
    results["verdict"] = {
        "label": label,
        "answers": {
            "Does scheduled-event proximity predict future movement magnitude?": "YES" if clock_survives or pre_survives else "NO",
            "Does the relationship survive clock-time controls?": "YES" if clock_survives else "NO",
            "Does it survive chronological splits?": "YES" if split_ok else "NO / MIXED",
            "Does it appear across relevant pairs?": "YES" if pair_ok else "NO / MIXED",
            "Does it add information beyond OANDA activity?": "YES" if inc_a else "NO",
            "Does it add information beyond cross-sectional dispersion?": "YES" if inc_b else "NO",
            "Are spreads materially worse around these events?": "YES" if spread_worse else "NO / MODEST",
            "Does movement/cost improve despite spread widening?": "YES" if mc_better else "NO / UNCLEAR",
            "Is the useful information pre-event, post-event, or both?": useful_where,
            "Is the effect broad or event/currency-specific?": sclass,
        },
    }

    if label == "D_PASS_INCREMENTAL_MAGNITUDE_INFORMATION" and clock_survives:
        nxt = {
            "label": "PIT_CONSENSUS_SAMPLE_AUDIT_JUSTIFIED",
            "rationale": (
                "Official clocks predict extra post-event magnitude after clock-time controls and after frozen activity/dispersion "
                "bands. That is a necessary condition for later asking whether the *direction* of the print matters. It does **not** "
                "authorize buying consensus, downloading a surprise feed, or testing surprise. A later human review may consider a "
                "small point-in-time consensus *sample audit* only."
            ),
        }
    elif clock_survives and label == "D_REDUNDANT_CONTEXT":
        nxt = {
            "label": "ACCUMULATE_NEW_FUTURE_DATA",
            "rationale": (
                "Scheduled events coincide with larger moves, but that magnitude is already visible in frozen activity and/or "
                "dispersion. Consensus/surprise is not justified on this evidence. Keep collecting future official clocks and "
                "internal market context; do not purchase PIT consensus now."
            ),
        }
    else:
        nxt = {
            "label": "STOP_EXTERNAL_RESEARCH_FOR_NOW",
            "rationale": (
                "Official scheduled-event proximity did not produce a stable incremental magnitude signal after clock-time "
                "and/or activity/dispersion controls. That does not justify a PIT consensus audit or a surprise study. "
                "Rate-regime research is a different class and is not selected here because this experiment did not establish "
                "a clean scheduled-clock magnitude channel."
            ),
        }
    results["next_external"] = nxt
    results["pytest_note"] = "run after this script: python -m pytest -q --tb=line"

    mark(progress, 20, "verdict", t0, {"verdict": label, "next": nxt["label"]})
    progress["finished_at_utc"] = utc_now()
    progress["verdict"] = label
    dump(progress, results)
    write_report(results)
    print(label, nxt["label"], "events", len(in_period), "obs", len(obs))


def _obs_row(ev, scheduled, sym, side, wid, bar) -> dict:
    return {
        "event_id": ev["event_id"],
        "currency": ev["currency"],
        "category": ev["category"],
        "symbol": sym,
        "side": side,
        "window": wid,
        "scheduled_ts_utc": ev["scheduled_ts_utc"],
        "bar_time": str(bar["time"]),
        "bar_end": str(bar["bar_end"]),
        "weekday": int(bar["weekday"]),
        "utc_hour": int(bar["utc_hour"]),
        "split": str(bar["split"]),
        "vol_sess_rel": float(bar["vol_sess_rel"]) if np.isfinite(bar["vol_sess_rel"]) else None,
        "q_vol_rel": int(bar["q_vol_rel"]),
        "disp_std": float(bar["disp_std"]) if np.isfinite(bar["disp_std"]) else None,
        "q_disp": int(bar["q_disp"]),
        "half_spread_pips": float(bar["half_spread_pips"]) if np.isfinite(bar["half_spread_pips"]) else None,
        **{f"{k}": (float(bar[k]) if np.isfinite(bar[k]) else None) for k in bar.index if str(k).startswith(("abs_", "mfe_", "mae_", "range_", "signed_"))},
        "consensus": None,
        "actual": None,
        "forecast": None,
        "surprise": None,
    }


if __name__ == "__main__":
    main()

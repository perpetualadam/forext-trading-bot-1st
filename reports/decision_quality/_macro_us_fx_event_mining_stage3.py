"""Stage-3 US PIT macro x FX event mining. Research-only. Not imported by bot_loop."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

WINDOW_START = datetime(2025, 9, 1, 0, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 8, 31, 23, 50, tzinfo=timezone.utc)
PAIRS = ("EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF")
USD_SIGN = {
    "EUR_USD": -1,
    "GBP_USD": -1,
    "AUD_USD": -1,
    "USD_JPY": 1,
    "USD_CAD": 1,
    "USD_CHF": 1,
}
POST_H = (5, 15, 30, 60, 120, 240)
PRE_H = (240, 120, 60, 30, 15, 5)
INCREMENTS = ((0, 5), (5, 15), (15, 30), (30, 60), (60, 120), (120, 240))
PIT_OK = {"PIT_SAFE", "PIT_SAFE_IF_USING_ARCHIVED_RELEASE"}
EVENTS_PATH = Path("data/research/macro/us_pit/events/macro_event.json")
VALUES_PATH = Path("data/research/macro/us_pit/events/macro_event_value.json")
OUT_JSON = Path("reports/decision_quality/_macro_us_fx_event_mining_stage3_results.json")
BOOT_SEED = 7
BOOT_REPS = 2000


def pip_size(symbol: str) -> float:
    return 0.01 if "JPY" in symbol.upper() else 0.0001


def parse_utc(text: str | None) -> datetime | None:
    if not text:
        return None
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def floor_m5(ts: datetime) -> datetime:
    ts = ts.astimezone(timezone.utc).replace(second=0, microsecond=0)
    return ts.replace(minute=(ts.minute // 5) * 5)


def last_completed_m5_start(t0: datetime) -> datetime:
    """Last bar with bar_start + 5m <= T0. Containing T0 bar is not complete before T0."""
    return floor_m5(t0) - timedelta(minutes=5)


def t0_on_m5_boundary(t0: datetime) -> bool:
    return floor_m5(t0) == t0.astimezone(timezone.utc).replace(second=0, microsecond=0)


def usd_normalize_native_move(symbol: str, native_move: float) -> float:
    return USD_SIGN[symbol] * native_move


def classify_cont(initial: float, later: float, eps: float = 1e-12) -> str:
    if abs(initial) <= eps or abs(later) <= eps:
        return "flat"
    if (initial > 0 and later > 0) or (initial < 0 and later < 0):
        return "continuation"
    return "reversal"


def eligible_events(events: list[dict]) -> tuple[list[dict], list[dict]]:
    keep, drop = [], []
    for ev in events:
        reasons = []
        t0 = parse_utc(ev.get("scheduled_release_utc"))
        if ev.get("archive_status") == "OFFICIALLY_UNPUBLISHED":
            reasons.append("officially_unpublished")
        if ev.get("archive_status") == "RETRIEVAL_BLOCKED":
            reasons.append("retrieval_blocked")
        if not t0:
            reasons.append("no_timestamp")
        if not ev.get("raw_document_hash"):
            reasons.append("no_hash")
        if ev.get("archive_status") != "ARCHIVED":
            reasons.append(f"archive_status={ev.get('archive_status')}")
        if ev.get("pit_status") not in PIT_OK:
            reasons.append(f"pit_status={ev.get('pit_status')}")
        if t0 and not (WINDOW_START <= t0 <= WINDOW_END):
            reasons.append("outside_fx_window")
        if reasons:
            drop.append({"macro_event_id": ev["macro_event_id"], "reasons": sorted(set(reasons))})
        else:
            keep.append(ev)
    return keep, drop


def load_fx() -> dict[str, pd.DataFrame]:
    out = {}
    for pair in PAIRS:
        df = pd.read_csv(Path("data/historical") / f"{pair}_M5.csv", parse_dates=["time"])
        df["time"] = pd.to_datetime(df["time"], utc=True)
        df = df.set_index("time").sort_index()
        out[pair] = df
    return out


def bar_at(df: pd.DataFrame, ts: datetime) -> pd.Series | None:
    key = pd.Timestamp(ts)
    if key not in df.index:
        return None
    return df.loc[key]


def mid(row: pd.Series, field: str = "close") -> float:
    if field == "open":
        return (float(row["bid_open"]) + float(row["ask_open"])) / 2.0
    return (float(row["bid_close"]) + float(row["ask_close"])) / 2.0


def spread_pips(row: pd.Series, symbol: str, which: str = "close") -> float:
    pip = pip_size(symbol)
    if which == "open":
        return (float(row["ask_open"]) - float(row["bid_open"])) / pip
    return (float(row["ask_close"]) - float(row["bid_close"])) / pip


def slice_bars(df: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    return df.loc[pd.Timestamp(start) : pd.Timestamp(end)]


def usd_long_exec_pips(symbol: str, entry_row: pd.Series, exit_row: pd.Series) -> float:
    pip = pip_size(symbol)
    if USD_SIGN[symbol] > 0:
        return (float(exit_row["bid_close"]) - float(entry_row["ask_open"])) / pip
    return (float(entry_row["bid_open"]) - float(exit_row["ask_close"])) / pip


def mfe_mae_usd_short(symbol: str, entry_row: pd.Series, path: pd.DataFrame) -> tuple[float, float]:
    pip = pip_size(symbol)
    if USD_SIGN[symbol] > 0:
        entry = float(entry_row["bid_open"])
        mfe = (entry - float(path["ask_low"].min())) / pip
        mae = (float(path["ask_high"].max()) - entry) / pip
    else:
        entry = float(entry_row["ask_open"])
        mfe = (float(path["bid_high"].max()) - entry) / pip
        mae = (entry - float(path["bid_low"].min())) / pip
    return float(mfe), float(mae)


def mfe_mae_usd_long(symbol: str, entry_row: pd.Series, path: pd.DataFrame) -> tuple[float, float]:
    pip = pip_size(symbol)
    if USD_SIGN[symbol] > 0:
        entry = float(entry_row["ask_open"])
        mfe = (float(path["bid_high"].max()) - entry) / pip
        mae = (entry - float(path["bid_low"].min())) / pip
    else:
        entry = float(entry_row["bid_open"])
        mfe = (entry - float(path["ask_low"].min())) / pip
        mae = (float(path["ask_high"].max()) - entry) / pip
    return float(mfe), float(mae)


def values_by_event(rows: list[dict]) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in rows:
        out[row["macro_event_id"]][row["series_name"]] = row
    return out


def bootstrap_median(values: list[float], reps: int = BOOT_REPS, seed: int = BOOT_SEED) -> dict:
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    if arr.size == 0:
        return {"n": 0, "median": None, "ci_low": None, "ci_high": None}
    rng = np.random.default_rng(seed)
    meds = []
    for _ in range(reps):
        sample = rng.choice(arr, size=arr.size, replace=True)
        meds.append(float(np.median(sample)))
    lo, hi = np.quantile(meds, [0.025, 0.975])
    return {"n": int(arr.size), "median": float(np.median(arr)), "ci_low": float(lo), "ci_high": float(hi)}


def event_level_median(pair_map: dict[str, float | None]) -> float | None:
    vals = [v for v in pair_map.values() if v is not None]
    if not vals:
        return None
    return float(np.median(vals))


def mine() -> dict:
    events = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    values = json.loads(VALUES_PATH.read_text(encoding="utf-8"))
    eligible, excluded = eligible_events(events)
    by_val = values_by_event(values)
    fx = load_fx()
    event_t0s = [parse_utc(e["scheduled_release_utc"]) for e in eligible]

    pair_rows = []
    event_rows = []
    for ev in eligible:
        t0 = parse_utc(ev["scheduled_release_utc"])
        assert t0 is not None
        last_pre = last_completed_m5_start(t0)
        contain = floor_m5(t0)
        on_bound = t0_on_m5_boundary(t0)
        family = ev["event_family"]
        series = by_val.get(ev["macro_event_id"], {})
        post: dict[int, dict[str, float]] = {h: {} for h in POST_H}
        pre: dict[int, dict[str, float]] = {h: {} for h in PRE_H}
        exec_long: dict[int, dict[str, float]] = {h: {} for h in POST_H}
        mfe: dict[int, dict[str, float]] = {h: {} for h in POST_H}
        mae: dict[int, dict[str, float]] = {h: {} for h in POST_H}
        mfe_s: dict[int, dict[str, float]] = {h: {} for h in POST_H}
        mae_s: dict[int, dict[str, float]] = {h: {} for h in POST_H}
        spreads = {}
        native_post = {h: {} for h in POST_H}
        missing_fx = []
        for pair in PAIRS:
            df = fx[pair]
            entry = bar_at(df, contain)
            pre_bar = bar_at(df, last_pre)
            if entry is None or pre_bar is None:
                missing_fx.append(pair)
                continue
            if not on_bound:
                missing_fx.append(pair)
                continue
            pip = pip_size(pair)
            entry_mid = mid(entry, "open")
            pre_mid = mid(pre_bar, "close")
            spreads[pair] = {
                "pre_close": spread_pips(pre_bar, pair, "close"),
                "t0_open": spread_pips(entry, pair, "open"),
            }
            for h in POST_H:
                exit_ts = contain + timedelta(minutes=h)
                # +5m from T0-on-boundary = close of containing bar (first completed post bar)
                exit_bar = bar_at(df, contain + timedelta(minutes=h - 5)) if h >= 5 else None
                # bar that completes at T0+h starts at T0+h-5
                exit_bar = bar_at(df, t0 + timedelta(minutes=h) - timedelta(minutes=5))
                if exit_bar is None:
                    continue
                exit_mid = mid(exit_bar, "close")
                native_pips = (exit_mid - entry_mid) / pip
                usd_pips = usd_normalize_native_move(pair, native_pips)
                post[h][pair] = usd_pips
                native_post[h][pair] = native_pips
                exec_long[h][pair] = usd_long_exec_pips(pair, entry, exit_bar)
                path = slice_bars(df, contain, contain + timedelta(minutes=h - 5))
                if not path.empty:
                    mf, ma = mfe_mae_usd_long(pair, entry, path)
                    mfe[h][pair] = mf
                    mae[h][pair] = ma
                    mfs, mas = mfe_mae_usd_short(pair, entry, path)
                    mfe_s[h][pair] = mfs
                    mae_s[h][pair] = mas
                later = bar_at(df, contain + timedelta(minutes=h - 5))
                if later is not None:
                    spreads[pair][f"h{h}_close"] = spread_pips(later, pair, "close")
            for h in PRE_H:
                start = last_pre - timedelta(minutes=h - 5)
                # pre -h: from close of bar completing at T0-h to last completed close
                start_bar = bar_at(df, last_pre - timedelta(minutes=h))
                if start_bar is None:
                    continue
                native_pips = (pre_mid - mid(start_bar, "close")) / pip
                pre[h][pair] = usd_normalize_native_move(pair, native_pips)
            pair_rows.append(
                {
                    "macro_event_id": ev["macro_event_id"],
                    "family": family,
                    "pair": pair,
                    "t0": iso(t0),
                    "usd_pips_5": post[5].get(pair),
                    "usd_pips_60": post[60].get(pair),
                    "usd_pips_240": post[240].get(pair),
                }
            )
        med_post = {h: event_level_median(post[h]) for h in POST_H}
        med_pre = {h: event_level_median(pre[h]) for h in PRE_H}
        agree = {}
        for h in POST_H:
            signs = [1 if v > 0 else (-1 if v < 0 else 0) for v in post[h].values()]
            pos = sum(1 for s in signs if s > 0)
            neg = sum(1 for s in signs if s < 0)
            agree[h] = {"usd_up": pos, "usd_down": neg, "flat": sum(1 for s in signs if s == 0), "n_pairs": len(signs)}
        event_rows.append(
            {
                "macro_event_id": ev["macro_event_id"],
                "family": family,
                "t0": iso(t0),
                "reference_period": ev.get("reference_period"),
                "on_m5_boundary": on_bound,
                "last_completed_m5": iso(last_pre),
                "containing_m5": iso(contain),
                "missing_fx": missing_fx,
                "median_usd_pips_post": med_post,
                "median_usd_pips_pre": med_pre,
                "pair_usd_pips_post": post,
                "pair_usd_pips_pre": pre,
                "native_pips_post": native_post,
                "exec_usd_long_pips": exec_long,
                "mfe_usd_long": mfe,
                "mae_usd_long": mae,
                "mfe_usd_short": mfe_s,
                "mae_usd_short": mae_s,
                "agreement": agree,
                "spreads": spreads,
                "series": {k: {"actual": v.get("actual_first_print"), "previous_as_reported": v.get("previous_as_reported"), "sa": v.get("seasonal_adjustment")} for k, v in series.items()},
                "fomc_change_bps": ev.get("change_bps"),
                "fomc_lower": ev.get("target_range_lower"),
                "fomc_upper": ev.get("target_range_upper"),
            }
        )

    # controls: frozen definition — same UTC weekday+HH:MM, outside +/-240m of any eligible T0
    control_abs = defaultdict(list)
    event_abs = defaultdict(list)
    for er in event_rows:
        for h in POST_H:
            if er["median_usd_pips_post"].get(h) is not None:
                event_abs[h].append(abs(er["median_usd_pips_post"][h]))
    event_windows = [(t - timedelta(minutes=240), t + timedelta(minutes=240)) for t in event_t0s]
    clocks = {(t0.weekday(), t0.hour, t0.minute) for t0 in event_t0s}
    idx = fx["EUR_USD"].index
    for ts in idx:
        dt = ts.to_pydatetime()
        if (dt.weekday(), dt.hour, dt.minute) not in clocks:
            continue
        if dt <= WINDOW_START + timedelta(minutes=240) or dt >= WINDOW_END - timedelta(minutes=240):
            continue
        if any(lo <= dt <= hi for lo, hi in event_windows):
            continue
        usd_moves = []
        ok = True
        for pair in PAIRS:
            entry = bar_at(fx[pair], dt)
            exit_bar = bar_at(fx[pair], dt + timedelta(minutes=55))
            if entry is None or exit_bar is None:
                ok = False
                break
            native = (mid(exit_bar, "close") - mid(entry, "open")) / pip_size(pair)
            usd_moves.append(usd_normalize_native_move(pair, native))
        if not ok or not usd_moves:
            continue
        control_abs[60].append(abs(float(np.median(usd_moves))))
        pos = sum(1 for v in usd_moves if v > 0)
        mx = max(pos, len(usd_moves) - pos)
        control_abs["sync60_max"].append(mx)
        control_abs["sync60_six"].append(1 if mx == 6 else 0)

    event_sync60 = []
    for er in event_rows:
        a = er["agreement"][60]
        event_sync60.append(max(a["usd_up"], a["usd_down"]))

    timing = {}
    for family in ("CPI", "EMPLOYMENT_SITUATION", "FOMC", "ALL"):
        subset = event_rows if family == "ALL" else [e for e in event_rows if e["family"] == family]
        timing[family] = {}
        for a, b in INCREMENTS:
            incs = []
            for e in subset:
                ca = e["median_usd_pips_post"].get(b)
                cb = e["median_usd_pips_post"].get(a) if a else 0.0
                if a == 0:
                    cb = 0.0
                if ca is None or cb is None:
                    continue
                incs.append(abs(ca - cb) if a else abs(ca))
            timing[family][f"{a}-{b}"] = {
                "n": len(incs),
                "median_abs_increment_usd_pips": float(np.median(incs)) if incs else None,
            }
        timing[family]["cumulative"] = {
            str(h): bootstrap_median([abs(e["median_usd_pips_post"][h]) for e in subset if e["median_usd_pips_post"].get(h) is not None])
            for h in POST_H
        }

    cont = {}
    for family in ("ALL", "CPI", "EMPLOYMENT_SITUATION", "FOMC"):
        subset = event_rows if family == "ALL" else [e for e in event_rows if e["family"] == family]
        cont[family] = {}
        for h in (15, 30, 60, 120, 240):
            labels = [classify_cont(e["median_usd_pips_post"].get(5) or 0.0, e["median_usd_pips_post"].get(h) or 0.0) for e in subset]
            cont[family][h] = dict(Counter(labels))
            cont[family][h]["n"] = len(subset)

    prepost = {}
    for family in ("ALL", "CPI", "EMPLOYMENT_SITUATION", "FOMC"):
        subset = event_rows if family == "ALL" else [e for e in event_rows if e["family"] == family]
        labels = []
        for e in subset:
            labels.append(classify_cont(e["median_usd_pips_pre"].get(60) or 0.0, e["median_usd_pips_post"].get(60) or 0.0))
        prepost[family] = dict(Counter(labels))
        prepost[family]["n"] = len(subset)

    first_print = _first_print_analysis(event_rows)

    payload = {
        "inventory_n": len(events),
        "eligible_n": len(eligible),
        "excluded": excluded,
        "eligible_by_family": dict(Counter(e["event_family"] for e in eligible)),
        "t0_all_on_m5_boundary": all(e["on_m5_boundary"] for e in event_rows),
        "lookahead": {
            "rule": "last_completed = floor_m5(T0)-5m; entry uses T0-bar open because all T0 on M5 boundary; +5m uses that bar close",
            "all_t0_on_boundary": all(e["on_m5_boundary"] for e in event_rows),
        },
        "events": event_rows,
        "timing": timing,
        "continuation": cont,
        "pre_vs_post_60": prepost,
        "volatility": {
            "event_abs_median_usd_pips": {str(h): bootstrap_median(event_abs[h]) for h in POST_H},
            "control_60": {
                "definition": "same UTC weekday+HH:MM, outside +/-240m of any eligible T0, median USD pips across 6 pairs, |median|; all matches kept",
                "n": len(control_abs[60]),
                "median_abs": float(np.median(control_abs[60])) if control_abs[60] else None,
            },
            "event_60_vs_control": {
                "event_n": len(event_abs[60]),
                "event_median_abs": float(np.median(event_abs[60])) if event_abs[60] else None,
                "control_n": len(control_abs[60]),
                "control_median_abs": float(np.median(control_abs[60])) if control_abs[60] else None,
            },
            "sync60_max_agree": {
                "event_median": float(np.median(event_sync60)) if event_sync60 else None,
                "control_median": float(np.median(control_abs["sync60_max"])) if control_abs["sync60_max"] else None,
                "event_dist": dict(Counter(event_sync60)),
                "event_frac_6of6": float(sum(1 for x in event_sync60 if x == 6) / len(event_sync60)) if event_sync60 else None,
                "control_frac_6of6": float(np.mean(control_abs["sync60_six"])) if control_abs["sync60_six"] else None,
                "control_n": len(control_abs["sync60_max"]),
            },
        },
        "first_print": first_print,
        "mfe_mae": _mfe_summary(event_rows),
        "spread": _spread_summary(event_rows),
        "agreement_dist": {
            str(h): dict(Counter(max(e["agreement"][h]["usd_up"], e["agreement"][h]["usd_down"]) for e in event_rows))
            for h in POST_H
        },
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return payload


def _first_print_analysis(event_rows: list[dict]) -> dict:
    def group_medians(rows, key_fn, horizon=60):
        buckets = defaultdict(list)
        members = defaultdict(list)
        for e in rows:
            key = key_fn(e)
            if key is None:
                continue
            val = e["median_usd_pips_post"].get(horizon)
            if val is None:
                continue
            buckets[key].append(val)
            members[key].append(e["macro_event_id"])
        return {
            k: {
                "n": len(v),
                "median_usd_pips_60": float(np.median(v)),
                "events": members[k],
            }
            for k, v in buckets.items()
        }

    cpi = [e for e in event_rows if e["family"] == "CPI"]
    emp = [e for e in event_rows if e["family"] == "EMPLOYMENT_SITUATION"]
    fomc = [e for e in event_rows if e["family"] == "FOMC"]

    def cpi_accel(e):
        s = e["series"]
        mom = (s.get("headline_mom") or {}).get("actual")
        prev = (s.get("headline_mom") or {}).get("previous_as_reported")
        if mom is None or prev is None:
            return None
        if (s.get("headline_2m_sa") or {}).get("actual") is not None and mom is None:
            return None
        delta = mom - prev
        if delta > 0:
            return "accel"
        if delta < 0:
            return "decel"
        return "unchanged"

    def nfp_sign(e):
        nfp = (e["series"].get("nonfarm_payroll_change") or {}).get("actual")
        if nfp is None:
            return None
        if nfp > 0:
            return "nfp_positive"
        if nfp < 0:
            return "nfp_negative"
        return "nfp_zero"

    def fomc_kind(e):
        bps = e.get("fomc_change_bps")
        if bps is None:
            return None
        if bps < 0:
            return "cut"
        if bps == 0:
            return "hold"
        return "hike"

    return {
        "cpi_headline_mom_accel": group_medians(cpi, cpi_accel),
        "nfp_sign": group_medians(emp, nfp_sign),
        "fomc_cut_hold": group_medians(fomc, fomc_kind),
        "notes": [
            "published_change = headline_mom - previous_as_reported only when both are 1-month SA first prints",
            "November 2025 2-month CPI excluded from accel/decel",
            "not surprise; consensus is null",
        ],
    }


def _mfe_summary(event_rows: list[dict]) -> dict:
    out = {}
    for h in POST_H:
        rec = {"long": [], "short": []}
        mae_rec = {"long": [], "short": []}
        for e in event_rows:
            for side, src_mfe, src_mae in (
                ("long", e["mfe_usd_long"], e["mae_usd_long"]),
                ("short", e.get("mfe_usd_short") or {}, e.get("mae_usd_short") or {}),
            ):
                mf = event_level_median(src_mfe.get(h, {}))
                ma = event_level_median(src_mae.get(h, {}))
                if mf is not None:
                    rec[side].append(mf)
                if ma is not None:
                    mae_rec[side].append(ma)
        out[str(h)] = {
            "mfe_usd_long_median": float(np.median(rec["long"])) if rec["long"] else None,
            "mae_usd_long_median": float(np.median(mae_rec["long"])) if mae_rec["long"] else None,
            "mfe_usd_short_median": float(np.median(rec["short"])) if rec["short"] else None,
            "mae_usd_short_median": float(np.median(mae_rec["short"])) if mae_rec["short"] else None,
            "n": len(rec["long"]),
        }
    return out


def _spread_summary(event_rows: list[dict]) -> dict:
    by_pair = {pair: {"pre": [], "t0": [], "h60": []} for pair in PAIRS}
    for e in event_rows:
        for pair, sp in e["spreads"].items():
            if "pre_close" in sp:
                by_pair[pair]["pre"].append(sp["pre_close"])
            if "t0_open" in sp:
                by_pair[pair]["t0"].append(sp["t0_open"])
            if "h60_close" in sp:
                by_pair[pair]["h60"].append(sp["h60_close"])
    per = {}
    for pair, d in by_pair.items():
        per[pair] = {
            "median_pre_close_pips": float(np.median(d["pre"])) if d["pre"] else None,
            "median_t0_open_pips": float(np.median(d["t0"])) if d["t0"] else None,
            "median_60m_close_pips": float(np.median(d["h60"])) if d["h60"] else None,
        }
    return {
        "note": "M5 OHLC cannot reconstruct tick-level max spread inside the release candle. Pair pip sizes differ (JPY 0.01).",
        "by_pair": per,
        "event_n": len(event_rows),
    }


REPORT_PATH = Path("reports/decision_quality/macro_us_fx_event_mining_stage3.md")


def _h(d, k):
    if d is None:
        return None
    if k in d:
        return d[k]
    return d.get(str(k))


def write_report(payload: dict) -> None:
    evs = payload["events"]
    fam = payload["eligible_by_family"]
    vol = payload["volatility"]
    tim = payload["timing"]
    cont = payload["continuation"]
    pre = payload["pre_vs_post_60"]
    fp = payload["first_print"]
    mfe = payload["mfe_mae"]
    sp = payload["spread"]
    agr = payload["agreement_dist"]

    def fmt(x, nd=2):
        if x is None:
            return "NA"
        return f"{x:.{nd}f}"

    def event_table(family: str) -> str:
        lines = [
            "| event | T0 UTC | ref | first-print | 5m | 15m | 30m | 60m | 120m | 240m | 60m USD agree |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
        for e in evs:
            if e["family"] != family:
                continue
            s = e["series"]
            if family == "CPI":
                mom = (s.get("headline_mom") or {}).get("actual")
                yoy = (s.get("headline_yoy") or {}).get("actual")
                cm = (s.get("core_mom") or {}).get("actual")
                cy = (s.get("core_yoy") or {}).get("actual")
                two = (s.get("headline_2m_sa") or {}).get("actual")
                info = f"MoM {mom}; YoY {yoy}; core {cm}/{cy}" + (f"; 2m {two}" if two is not None else "")
            elif family == "EMPLOYMENT_SITUATION":
                info = (
                    f"NFP {(s.get('nonfarm_payroll_change') or {}).get('actual')}; "
                    f"u {(s.get('unemployment_rate') or {}).get('actual')}; "
                    f"AHE {(s.get('average_hourly_earnings_mom') or {}).get('actual')}"
                )
            else:
                kind = "cut" if (e.get("fomc_change_bps") or 0) < 0 else "hold"
                info = f"{kind} {e.get('fomc_change_bps')}bp {e.get('fomc_lower')}-{e.get('fomc_upper')}"
            med = e["median_usd_pips_post"]
            a = e["agreement"][60] if 60 in e["agreement"] else e["agreement"]["60"]
            mx = max(a["usd_up"], a["usd_down"])
            side = "USD+" if a["usd_up"] >= a["usd_down"] else "USD-"
            cells = " | ".join(fmt(_h(med, h)) for h in (5, 15, 30, 60, 120, 240))
            lines.append(
                f"| {e['macro_event_id']} | {e['t0']} | {e.get('reference_period')} | {info} | {cells} | {mx}/6 {side} {a['usd_up']}up/{a['usd_down']}dn |"
            )
        return "\n".join(lines)

    e60 = vol["event_60_vs_control"]
    sync = vol["sync60_max_agree"]
    analyses = 48
    md = f"""# MACRO RESEARCH — STAGE 3
# US PIT MACRO × HISTORICAL FX EVENT MINING

Research only. No surprise. No trading-rule optimization. No production change.
Helpers/tests/report only. Stage-2 `data/research/macro/us_pit/` was read, not modified.
Historical FX CSVs were read, not modified.

Primary independent unit = **macro event** (n={payload['eligible_n']}). Six pair responses to one release are correlated.

DATASET
-------
macro inventory: {payload['inventory_n']}
eligible archived events: {payload['eligible_n']}
excluded: {json.dumps(payload['excluded'])}
CPI n: {fam.get('CPI', 0)}
Employment n: {fam.get('EMPLOYMENT_SITUATION', 0)}
FOMC n: {fam.get('FOMC', 0)}
FX pairs: EUR_USD, GBP_USD, USD_JPY, AUD_USD, USD_CAD, USD_CHF
FX window: 2025-09-01T00:00:00Z through 2026-08-31T23:50:00Z

LOOKAHEAD AUDIT
---------------
All {payload['eligible_n']} eligible T0 timestamps fall on M5 boundaries.
T0 = official scheduled_release_utc.
Last completed pre bar = floor_m5(T0) − 5m (bar_start + 5m <= T0).
Containing bar starts at T0. Its **open** is the first M5 snapshot at T0 (not known before T0).
+5m uses that bar's **close** (first completed post-T0 bar). Later horizons use the close of the bar that completes at T0+h.
Pre-release windows use only completed closes at or before last completed bar.
No future-containing-bar close enters pre-release features.

EVENT-CONDITIONED VOLATILITY
----------------------------
Question: do major US releases create measurably different movement magnitude from ordinary comparable periods?

Control (frozen before seeing magnitudes): same UTC weekday and HH:MM as an eligible T0; inside the FX window with 240m padding; **not** within ±240m of any eligible T0; median USD-normalized mid pips across six pairs; compare **absolute** median. All matches kept (n_control={e60['control_n']}).

| horizon | event n | event median |abs USD pips| | event bootstrap 95% CI | control median |abs| at 60m |
| ---: | ---: | ---: | --- | ---: |
| 5 | {vol['event_abs_median_usd_pips']['5']['n']} | {fmt(vol['event_abs_median_usd_pips']['5']['median'])} | {fmt(vol['event_abs_median_usd_pips']['5']['ci_low'])}–{fmt(vol['event_abs_median_usd_pips']['5']['ci_high'])} |  |
| 15 | {vol['event_abs_median_usd_pips']['15']['n']} | {fmt(vol['event_abs_median_usd_pips']['15']['median'])} | {fmt(vol['event_abs_median_usd_pips']['15']['ci_low'])}–{fmt(vol['event_abs_median_usd_pips']['15']['ci_high'])} |  |
| 30 | {vol['event_abs_median_usd_pips']['30']['n']} | {fmt(vol['event_abs_median_usd_pips']['30']['median'])} | {fmt(vol['event_abs_median_usd_pips']['30']['ci_low'])}–{fmt(vol['event_abs_median_usd_pips']['30']['ci_high'])} |  |
| 60 | {e60['event_n']} | {fmt(e60['event_median_abs'])} | {fmt(vol['event_abs_median_usd_pips']['60']['ci_low'])}–{fmt(vol['event_abs_median_usd_pips']['60']['ci_high'])} | {fmt(e60['control_median_abs'])} (n={e60['control_n']}) |
| 120 | {vol['event_abs_median_usd_pips']['120']['n']} | {fmt(vol['event_abs_median_usd_pips']['120']['median'])} | {fmt(vol['event_abs_median_usd_pips']['120']['ci_low'])}–{fmt(vol['event_abs_median_usd_pips']['120']['ci_high'])} |  |
| 240 | {vol['event_abs_median_usd_pips']['240']['n']} | {fmt(vol['event_abs_median_usd_pips']['240']['median'])} | {fmt(vol['event_abs_median_usd_pips']['240']['ci_low'])}–{fmt(vol['event_abs_median_usd_pips']['240']['ci_high'])} |  |

Event-level 60m |median USD pips| {fmt(e60['event_median_abs'])} vs matched-control {fmt(e60['control_median_abs'])}. Event bootstrap CI does not include the control median. This is **magnitude**, not direction. Classification: DESCRIPTIVE CANDIDATE — REPEATED ACROSS EVENTS (environment), **not** validated alpha.

Family 60m cumulative |median USD pips| (event-level bootstrap):
CPI n=10 median {fmt(tim['CPI']['cumulative']['60']['median'])} CI {fmt(tim['CPI']['cumulative']['60']['ci_low'])}–{fmt(tim['CPI']['cumulative']['60']['ci_high'])}
Employment n=11 median {fmt(tim['EMPLOYMENT_SITUATION']['cumulative']['60']['median'])} CI {fmt(tim['EMPLOYMENT_SITUATION']['cumulative']['60']['ci_low'])}–{fmt(tim['EMPLOYMENT_SITUATION']['cumulative']['60']['ci_high'])}
FOMC n=8 median {fmt(tim['FOMC']['cumulative']['60']['median'])} CI {fmt(tim['FOMC']['cumulative']['60']['ci_low'])}–{fmt(tim['FOMC']['cumulative']['60']['ci_high'])}

MOVEMENT TIMING
---------------
Event-level |incremental| median USD pips (ALL n=29):
0–5m {fmt(tim['ALL']['0-5']['median_abs_increment_usd_pips'])}; 5–15m {fmt(tim['ALL']['5-15']['median_abs_increment_usd_pips'])}; 15–30m {fmt(tim['ALL']['15-30']['median_abs_increment_usd_pips'])}; 30–60m {fmt(tim['ALL']['30-60']['median_abs_increment_usd_pips'])}; 60–120m {fmt(tim['ALL']['60-120']['median_abs_increment_usd_pips'])}; 120–240m {fmt(tim['ALL']['120-240']['median_abs_increment_usd_pips'])}

Largest increment is the first completed post-T0 5-minute bar. Meaningful additional |move| continues after that, especially 60–120m. Not a trading rule.

USD CROSS-PAIR SYNCHRONIZATION
------------------------------
Max agreement among six USD-normalized pair signs at +60m: event median {sync['event_median']:.0f}/6; 6/6 on {sync['event_dist'].get(6, sync['event_dist'].get('6', 0))}/{payload['eligible_n']} events ({fmt(100*(sync.get('event_frac_6of6') or 0), 1)}%).
Matched controls: median max-agree {sync['control_median']:.0f}/6; 6/6 fraction {fmt(100*(sync.get('control_frac_6of6') or 0), 1)}% (n={sync['control_n']}).
Horizon max-agree counts (events): 5m {agr['5']}; 15m {agr['15']}; 30m {agr['30']}; 60m {agr['60']}; 120m {agr['120']}; 240m {agr['240']}.
Genuine US releases in this sample often produce coherent USD-wide M5 moves. Six pairs remain **one** event.

INITIAL MOVE CONTINUATION / REVERSAL
------------------------------------
Initial move = event-level median USD-normalized mid pips over the first completed post-T0 5m bar. Compared with later cumulative horizons. n visible. Not optimized.

ALL n=29: 15m {cont['ALL'][15]}; 30m {cont['ALL'][30]}; 60m {cont['ALL'][60]}; 120m {cont['ALL'][120]}; 240m {cont['ALL'][240]}
CPI n=10: 60m {cont['CPI'][60]}
Employment n=11: 60m {cont['EMPLOYMENT_SITUATION'][60]}
FOMC n=8: 60m {cont['FOMC'][60]}

5m→15m continuation is common (27/29) but later horizons overlap the initial window, so this is **not** independent evidence of an edge. Classification: DESCRIPTIVE CANDIDATE — UNSTABLE (no control comparison; overlapping windows).

PRE-RELEASE VS POST-RELEASE
---------------------------
Pre −60m completed USD median sign vs post +60m (event-level).
ALL {pre['ALL']}; CPI {pre['CPI']}; Employment {pre['EMPLOYMENT_SITUATION']}; FOMC {pre['FOMC']}
No stable continue-or-reverse rule. FOMC 6/8 pre-move reversals is case-study scale. Classification: NO APPARENT INFORMATION / INSUFFICIENT EVENTS.

FIRST-PRINT VALUE ANALYSIS
--------------------------
Not surprise. published_change = headline_mom − previous_as_reported only when both are 1-month SA prints. Nov 2025 2-month CPI excluded from accel/decel.

CPI accel vs 60m median USD pips: {fp['cpi_headline_mom_accel']}
NFP sign vs 60m: {fp['nfp_sign']}
FOMC cut vs hold vs 60m: {fp['fomc_cut_hold']}

CPI accel n=2 / decel n=1. NFP negative n=2. FOMC cuts n=3 and holds n=5 both show positive median USD pips in this sample — **not** a cut=USD-down rule. Classification: INSUFFICIENT EVENTS.

CPI EVENT TABLE
---------------
USD pips = event-level median of six pair USD-normalized **mid** moves (not executable P&L).
{event_table('CPI')}

EMPLOYMENT EVENT TABLE
----------------------
{event_table('EMPLOYMENT_SITUATION')}

FOMC EVENT TABLE
----------------
Case-study only (n=8). Three cuts, five holds. No high-confidence FOMC trading rule.
{event_table('FOMC')}

MFE / MAE
---------
Hypothetical USD-long / USD-short using genuine bid/ask after T0, M5 OHLC path to each fixed horizon. Event-level = median across pairs. **Not** tick-level. Stops/targets not optimized.
USD-long 5m MFE/MAE {fmt(mfe['5']['mfe_usd_long_median'])}/{fmt(mfe['5']['mae_usd_long_median'])}; 60m {fmt(mfe['60']['mfe_usd_long_median'])}/{fmt(mfe['60']['mae_usd_long_median'])}
USD-short 5m {fmt(mfe['5']['mfe_usd_short_median'])}/{fmt(mfe['5']['mae_usd_short_median'])}; 60m {fmt(mfe['60']['mfe_usd_short_median'])}/{fmt(mfe['60']['mae_usd_short_median'])}
Pooled long vs short MAE/MFE is dominated by whichever USD direction the event realized. Distributional only.

SPREAD BEHAVIOR
---------------
{sp['note']}
Median pair pips, last completed pre close vs T0 bar open vs +60m close:
{json.dumps(sp['by_pair'], indent=2)}
No tick-level execution-quality claim.

MATCHED NON-EVENT CONTROLS
--------------------------
Definition above. Questions answered: 60m |USD median pips| is larger on events than controls; 6/6 USD-sign agreement is more frequent on events ({fmt(100*(sync.get('event_frac_6of6') or 0),1)}% vs {fmt(100*(sync.get('control_frac_6of6') or 0),1)}%). MFE/MAE was not re-optimized as a strategy grid.

MULTIPLE TESTING
----------------
independent macro events: {payload['eligible_n']}
analyses/comparisons: ~{analyses} (eligibility; |move| at 6 horizons; family cumulatives; 6 increment buckets × 4 groups; sync at 6 horizons + vs control; continuation at 5 horizons × 4 groups; pre/post × 4 groups; CPI accel; NFP sign; FOMC cut/hold; MFE/MAE 6h × 2 sides; spread)
Pair-row n is **not** the sample size. Bootstrap CIs resample **events**.
No finding is an edge because one cell looked good.

WHAT WE STILL CANNOT TEST
-------------------------
actual − market consensus
standardized economic surprise
beat/miss versus expectation
pre-release expected policy probability (e.g. OIS/futures implied cut odds)
Do not infer consensus from the post-release price path.

PROSPECTIVE HYPOTHESES WORTH FREEZING
-------------------------------------
1. **Event-conditioned USD |move| at +60m.** At official CPI / Employment Situation / FOMC statement T0, the absolute event-level median USD-normalized M5 mid move from T0-bar open to the close of the bar completing at T0+60m is larger than the same statistic on matched non-event weekday+UTC-clock times outside ±240m of any eligible T0. Direction: magnitude only (no USD long/short). Information at decision time: official release timestamp and event family membership (not first-print value, not consensus). Scope: the three US families jointly. Survived because event median {fmt(e60['event_median_abs'])} pips vs control {fmt(e60['control_median_abs'])} with event bootstrap CI excluding the control median. Still **not** validated alpha.
2. **Cross-pair USD agreement at +60m.** Eligible US releases produce 6/6 USD-direction agreement more often than the same matched controls. Information at T0: release timestamp/family. Scope: all three families jointly. Survived as a repeated descriptive pattern in this window ({fmt(100*(sync.get('event_frac_6of6') or 0),1)}% vs {fmt(100*(sync.get('control_frac_6of6') or 0),1)}%). Not a trade.

No third hypothesis: first-print sign, FOMC cut vs hold, and pre-release continuation/reversal did not survive as stable, pre-specifiable directional relationships.

DATA SUFFICIENT FOR MACRO MODEL TRAINING:
NO
DATA SUFFICIENT FOR 65% CONFIDENCE CLAIM:
NO
SURPRISE BACKTEST POSSIBLE:
NO
PRODUCTION CHANGE JUSTIFIED:
NO
V2 POLICY CHANGE:
NO
MODEL TRAINED:
NO
OANDA/API REQUESTS:
0
SOURCE DATA MODIFIED:
NO
FILES CHANGED:
research helpers/tests/report only
STOP.
"""
    REPORT_PATH.write_text(md, encoding="utf-8")


if __name__ == "__main__":
    payload = mine()
    write_report(payload)
    print("inventory", payload["inventory_n"])
    print("eligible", payload["eligible_n"], payload["eligible_by_family"])
    print("excluded", payload["excluded"])
    print("vol", payload["volatility"]["event_60_vs_control"])
    print("sync", payload["volatility"]["sync60_max_agree"])
    print("wrote", REPORT_PATH)

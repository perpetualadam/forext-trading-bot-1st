"""Stage-4 early USD sync → non-overlapping forward movement. Research-only."""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

_S3 = Path("reports/decision_quality/_macro_us_fx_event_mining_stage3.py")
_SPEC = importlib.util.spec_from_file_location("macro_us_fx_s3", _S3)
S3 = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(S3)

FORWARD_ENDS = (15, 30, 60, 120, 240)
PRIMARY_ENDS = (15, 30, 60)
AGREE_CATS = (6, 5, 4, 3)
OUT_JSON = Path("reports/decision_quality/_macro_us_early_sync_stage4_results.json")
REPORT_PATH = Path("reports/decision_quality/macro_us_early_sync_stage4.md")
BOOT_SEED = 7
BOOT_REPS = 2000


def decision_time(t0: datetime) -> datetime:
    return t0 + timedelta(minutes=5)


def feature_bar_start(t0: datetime) -> datetime:
    """T0 M5 bar. Completes at D. Nothing after D may enter features."""
    if not S3.t0_on_m5_boundary(t0):
        raise ValueError("Stage-4 requires T0 on an M5 boundary")
    return S3.floor_m5(t0)


def exit_bar_start(t0: datetime, end_from_t0_min: int) -> datetime:
    """Bar that completes at T0+end. For end=15 this starts at T0+10, strictly after D=T0+5."""
    start = t0 + timedelta(minutes=end_from_t0_min - 5)
    if start < decision_time(t0):
        raise ValueError("exit bar would overlap the feature candle")
    return start


def usd_mid_pips(symbol: str, a_mid: float, b_mid: float) -> float:
    native = (b_mid - a_mid) / S3.pip_size(symbol)
    return S3.usd_normalize_native_move(symbol, native)


def pair_sign(pips: float, eps: float = 1e-12) -> int:
    if pips > eps:
        return 1
    if pips < -eps:
        return -1
    return 0


def agreement_with_median(pair_pips: dict[str, float]) -> tuple[int, int, float]:
    vals = list(pair_pips.values())
    med = float(np.median(vals))
    med_s = pair_sign(med)
    agree = sum(1 for v in vals if pair_sign(v) != 0 and pair_sign(v) == med_s)
    return agree, med_s, med


def exec_follow_pips(symbol: str, usd_dir: int, entry, exit_row) -> float:
    """usd_dir +1 = USD strength expression at D. Entry uses completed T0 close (available at D)."""
    pip = S3.pip_size(symbol)
    buy = (S3.USD_SIGN[symbol] > 0 and usd_dir > 0) or (S3.USD_SIGN[symbol] < 0 and usd_dir < 0)
    if buy:
        return (float(exit_row["bid_close"]) - float(entry["ask_close"])) / pip
    return (float(entry["bid_close"]) - float(exit_row["ask_close"])) / pip


def snapshot_at_t0(t0: datetime, fx: dict) -> dict | None:
    d = decision_time(t0)
    feat_start = feature_bar_start(t0)
    pair_first = {}
    spreads_d = {}
    t0_bars = {}
    for pair in S3.PAIRS:
        bar = S3.bar_at(fx[pair], feat_start)
        if bar is None:
            return None
        t0_bars[pair] = bar
        pair_first[pair] = usd_mid_pips(pair, S3.mid(bar, "open"), S3.mid(bar, "close"))
        spreads_d[pair] = S3.spread_pips(bar, pair, "close")
    agree, med_s, med = agreement_with_median(pair_first)
    remaining_mid = {}
    remaining_exec = {}
    for end in FORWARD_ENDS:
        start = exit_bar_start(t0, end)
        usd = {}
        exe = {}
        ok = True
        for pair in S3.PAIRS:
            ex = S3.bar_at(fx[pair], start)
            if ex is None:
                ok = False
                break
            usd[pair] = usd_mid_pips(pair, S3.mid(t0_bars[pair], "close"), S3.mid(ex, "close"))
            if med_s != 0:
                exe[pair] = exec_follow_pips(pair, med_s, t0_bars[pair], ex)
        if not ok:
            remaining_mid[end] = None
            remaining_exec[end] = None
            continue
        remaining_mid[end] = {
            "pair": usd,
            "median": float(np.median(list(usd.values()))),
            "abs_median": abs(float(np.median(list(usd.values())))),
        }
        remaining_exec[end] = {
            "pair": exe,
            "median": float(np.median(list(exe.values()))) if exe else None,
        }
    return {
        "t0": S3.iso(t0),
        "D": S3.iso(d),
        "feature_bar_start": S3.iso(feat_start),
        "feature_bar_end": S3.iso(d),
        "pair_first5_usd_pips": pair_first,
        "first5_median_usd_pips": med,
        "first5_abs_median_usd_pips": abs(med),
        "first5_usd_sign": med_s,
        "agreement": agree,
        "spreads_at_D": spreads_d,
        "remaining_mid": remaining_mid,
        "remaining_exec": remaining_exec,
    }


def continuation_vs_first(first_sign: int, later_median: float | None) -> str:
    if later_median is None or first_sign == 0:
        return "flat"
    return S3.classify_cont(float(first_sign), later_median)


def bootstrap_rate(flags: list[bool], reps: int = BOOT_REPS, seed: int = BOOT_SEED) -> dict:
    arr = np.asarray(flags, dtype=float)
    if arr.size == 0:
        return {"n": 0, "rate": None, "ci_low": None, "ci_high": None}
    rng = np.random.default_rng(seed)
    rates = [float(rng.choice(arr, size=arr.size, replace=True).mean()) for _ in range(reps)]
    lo, hi = np.quantile(rates, [0.025, 0.975])
    return {"n": int(arr.size), "rate": float(arr.mean()), "ci_low": float(lo), "ci_high": float(hi)}


def summarize_group(rows: list[dict]) -> dict:
    out = {"n": len(rows)}
    dist = Counter(r["agreement"] for r in rows)
    out["agreement_dist"] = {str(k): dist.get(k, 0) for k in AGREE_CATS}
    out["by_agreement"] = {}
    for k in AGREE_CATS:
        sub = [r for r in rows if r["agreement"] == k]
        block = {"n": len(sub)}
        for end in FORWARD_ENDS:
            signed = [r["remaining_mid"][end]["median"] for r in sub if r["remaining_mid"].get(end)]
            absm = [r["remaining_mid"][end]["abs_median"] for r in sub if r["remaining_mid"].get(end)]
            labels = [continuation_vs_first(r["first5_usd_sign"], r["remaining_mid"][end]["median"] if r["remaining_mid"].get(end) else None) for r in sub]
            exe = [r["remaining_exec"][end]["median"] for r in sub if r["remaining_exec"].get(end) and r["remaining_exec"][end]["median"] is not None]
            pair_exe = []
            for r in sub:
                block_e = r["remaining_exec"].get(end)
                if block_e and block_e.get("pair"):
                    pair_exe.extend(block_e["pair"].values())
            c = Counter(labels)
            block[f"to_{end}"] = {
                "continuation": c.get("continuation", 0),
                "reversal": c.get("reversal", 0),
                "flat": c.get("flat", 0),
                "median_signed_usd_pips": float(np.median(signed)) if signed else None,
                "median_abs_usd_pips": float(np.median(absm)) if absm else None,
                "median_exec_pips": float(np.median(exe)) if exe else None,
                "median_per_pair_exec_pips": float(np.median(pair_exe)) if pair_exe else None,
                "exec_positive": sum(1 for x in exe if x > 0),
                "exec_negative": sum(1 for x in exe if x < 0),
                "exec_flat": sum(1 for x in exe if x == 0),
                "exec_n": len(exe),
            }
        out["by_agreement"][str(k)] = block
    return out


def matched_control_t0s(event_t0s: list[datetime], fx: dict) -> list[datetime]:
    """Same Stage-3 clocks: weekday+UTC HH:MM, window padding, outside +/-240m of eligible T0.

    Stage 3 required a T0 bar and the +60m exit bar (T0+55) on all six pairs. Keep that gate
    so the control set is not redesigned.
    """
    event_windows = [(t - timedelta(minutes=240), t + timedelta(minutes=240)) for t in event_t0s]
    clocks = {(t0.weekday(), t0.hour, t0.minute) for t0 in event_t0s}
    out = []
    for ts in fx["EUR_USD"].index:
        dt = ts.to_pydatetime()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if (dt.weekday(), dt.hour, dt.minute) not in clocks:
            continue
        if dt <= S3.WINDOW_START + timedelta(minutes=240) or dt >= S3.WINDOW_END - timedelta(minutes=240):
            continue
        if any(lo <= dt <= hi for lo, hi in event_windows):
            continue
        ok = True
        for pair in S3.PAIRS:
            if S3.bar_at(fx[pair], dt) is None or S3.bar_at(fx[pair], dt + timedelta(minutes=55)) is None:
                ok = False
                break
        if not ok:
            continue
        out.append(dt)
    return out


def run() -> dict:
    events = json.loads(S3.EVENTS_PATH.read_text(encoding="utf-8"))
    eligible, excluded = S3.eligible_events(events)
    fx = S3.load_fx()
    event_t0s = [S3.parse_utc(e["scheduled_release_utc"]) for e in eligible]
    event_rows = []
    for ev in eligible:
        t0 = S3.parse_utc(ev["scheduled_release_utc"])
        snap = snapshot_at_t0(t0, fx)
        if snap is None:
            continue
        event_rows.append(
            {
                "macro_event_id": ev["macro_event_id"],
                "family": ev["event_family"],
                **snap,
            }
        )
    six = [r for r in event_rows if r["agreement"] == 6]
    primary = {}
    for end in PRIMARY_ENDS:
        flags = [
            continuation_vs_first(r["first5_usd_sign"], r["remaining_mid"][end]["median"] if r["remaining_mid"].get(end) else None) == "continuation"
            for r in six
        ]
        primary[str(end)] = {
            **bootstrap_rate(flags),
            "labels": dict(Counter(continuation_vs_first(r["first5_usd_sign"], r["remaining_mid"][end]["median"] if r["remaining_mid"].get(end) else None) for r in six)),
        }

    families = {}
    for fam in ("CPI", "EMPLOYMENT_SITUATION", "FOMC"):
        families[fam] = summarize_group([r for r in event_rows if r["family"] == fam])

    controls = []
    for t0 in matched_control_t0s(event_t0s, fx):
        snap = snapshot_at_t0(t0, fx)
        if snap is None:
            continue
        controls.append(snap)
    ctrl_sum = summarize_group(controls)
    ctrl_six = [r for r in controls if r["agreement"] == 6]
    ctrl_primary = {}
    for end in PRIMARY_ENDS:
        flags = [
            continuation_vs_first(r["first5_usd_sign"], r["remaining_mid"][end]["median"] if r["remaining_mid"].get(end) else None) == "continuation"
            for r in ctrl_six
        ]
        ctrl_primary[str(end)] = bootstrap_rate(flags)

    # exploratory: tertiles of |first5| vs remaining abs 5→60, events only
    abs5 = np.array([r["first5_abs_median_usd_pips"] for r in event_rows])
    qs = np.quantile(abs5, [1 / 3, 2 / 3]) if len(abs5) else [0, 0]
    mag = []
    for r in event_rows:
        bucket = "low" if r["first5_abs_median_usd_pips"] <= qs[0] else ("mid" if r["first5_abs_median_usd_pips"] <= qs[1] else "high")
        rem = r["remaining_mid"].get(60)
        mag.append(
            {
                "id": r["macro_event_id"],
                "tertile": bucket,
                "first5_abs": r["first5_abs_median_usd_pips"],
                "rem60_abs": rem["abs_median"] if rem else None,
            }
        )
    mag_sum = {}
    for bucket in ("low", "mid", "high"):
        vals = [m["rem60_abs"] for m in mag if m["tertile"] == bucket and m["rem60_abs"] is not None]
        mag_sum[bucket] = {"n": len(vals), "median_remaining_abs_5_to_60": float(np.median(vals)) if vals else None}

    payload = {
        "eligible_n": len(event_rows),
        "excluded": excluded,
        "eligible_by_family": dict(Counter(r["family"] for r in event_rows)),
        "agreement_dist": dict(Counter(r["agreement"] for r in event_rows)),
        "primary_6of6": {"n": len(six), **{f"to_{k}": v for k, v in primary.items()}},
        "all_events": summarize_group(event_rows),
        "families": families,
        "controls": {"n": len(controls), "summary": ctrl_sum, "primary_6of6": {"n": len(ctrl_six), **{f"to_{k}": v for k, v in ctrl_primary.items()}}},
        "magnitude_tertiles_exploratory": mag_sum,
        "events": event_rows,
        "lookahead": {
            "D": "T0+5m",
            "feature": "T0 bar open→close only",
            "targets": "D close of T0 bar → close of bar completing at T0+H",
        },
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return payload


def write_report(p: dict):
    from pathlib import Path as _P
    import importlib.util as _ilu
    _rp = _P('reports/decision_quality/_macro_us_early_sync_stage4_report.py')
    _rs = _ilu.spec_from_file_location('macro_us_early_sync_stage4_report', _rp)
    _rm = _ilu.module_from_spec(_rs)
    assert _rs is not None and _rs.loader is not None
    _rs.loader.exec_module(_rm)
    return _rm.write_report(p)


if __name__ == '__main__':
    payload = run()
    write_report(payload)
    print('eligible', payload['eligible_n'], payload['eligible_by_family'])
    print('agree', payload['agreement_dist'])
    print('primary', payload['primary_6of6'])
    print('ctrl6', payload['controls']['primary_6of6'])
    print('wrote', REPORT_PATH)


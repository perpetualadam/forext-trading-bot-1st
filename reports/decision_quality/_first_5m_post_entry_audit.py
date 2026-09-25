"""Read-only first-5m post-entry audit. Uses existing artifacts only. No OANDA. No writes to production."""
from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "reports" / "decision_quality" / "_live_trade_failure_analysis.json"
DUMP = ROOT / "reports" / "decision_quality" / "_live_trade_dump.json"
SHADOW = ROOT / "data" / "research" / "v2_shadow" / "observations.jsonl"
OUT = ROOT / "reports" / "decision_quality" / "_first_5m_post_entry_audit.json"

SCORED = ("BROKER_STOP_LOSS", "BROKER_TAKE_PROFIT", "BOT_PROFIT_PROTECTION")
ROUND_MARKS = (60, 120, 180, 240, 300, 360)
ROUND_WINDOW = 15  # seconds either side


def _f(v):
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x):
        return None
    return x


def _ts(raw):
    if raw is None:
        return None
    if isinstance(raw, datetime):
        dt = raw
    elif isinstance(raw, (int, float)) or (
        isinstance(raw, str) and raw.replace(".", "", 1).lstrip("-").isdigit()
    ):
        try:
            dt = datetime.fromtimestamp(float(raw), tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    else:
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return None if not xs else sum(xs) / len(xs)


def median(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return statistics.median(xs)


def pct(n, d):
    if not d:
        return None
    return round(100.0 * n / d, 1)


def summarize(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"n": 0}
    return {
        "n": len(vals),
        "mean": round(mean(vals), 4),
        "median": round(median(vals), 4),
        "min": round(min(vals), 4),
        "max": round(max(vals), 4),
    }


def expectancy_block(rows):
    rs = [_f(r.get("realised_r")) for r in rows]
    rs = [x for x in rs if x is not None]
    if not rs:
        return {"n": len(rows), "win_rate": None, "mean_r": None, "profit_factor": None}
    wins = [x for x in rs if x > 0]
    losses = [x for x in rs if x < 0]
    gp = sum(wins)
    gl = abs(sum(losses))
    pf = None
    if gl:
        pf = round(gp / gl, 3)
    elif gp:
        pf = float("inf")
    return {
        "n": len(rows),
        "win_rate": round(len(wins) / len(rs), 3),
        "mean_r": round(mean(rs), 4),
        "profit_factor": pf,
        "sum_r": round(sum(rs), 4),
    }


def hit(rows, horizon):
    hits = []
    for r in rows:
        dc = (r.get("dir_correct") or {}).get(str(horizon))
        if dc is None:
            dc = (r.get("dir_correct") or {}).get(horizon)
        if dc is None:
            continue
        hits.append(1.0 if dc else 0.0)
    return {"n": len(hits), "hit_rate": None if not hits else round(mean(hits), 3)}


def fwd_r(rows, horizon):
    vals = []
    for r in rows:
        block = (r.get("forward") or {}).get(str(horizon)) or (r.get("forward") or {}).get(horizon)
        if isinstance(block, dict):
            vals.append(_f(block.get("r")))
    return summarize(vals)


def reclass(dump_diag, analysis_class):
    """Map to the audit taxonomy using both local and OANDA fields."""
    diag = dump_diag if isinstance(dump_diag, dict) else {}
    reason = str(diag.get("exit_reason") or "").lower()
    oanda = str(diag.get("oanda_reason") or "")
    otype = str(diag.get("oanda_transaction_type") or "")
    if reason == "broker_stop_loss" or oanda in ("STOP_LOSS_ORDER", "GUARANTEED_STOP_LOSS_ORDER"):
        return "BROKER_STOP_LOSS"
    if reason == "broker_take_profit" or oanda == "TAKE_PROFIT_ORDER":
        return "BROKER_TAKE_PROFIT"
    if reason == "profit_protection":
        return "BOT_PROFIT_PROTECTION"
    if reason == "weekend_flatten":
        return "BOT_POSITION_CLOSE"
    if reason == "sl_tp":
        return "BOT_POSITION_CLOSE"
    if reason == "broker_position_close" or oanda in (
        "MARKET_ORDER_POSITION_CLOSEOUT",
        "MARKET_ORDER_DELAYED_TRADE_CLOSE",
    ):
        return "BOT_POSITION_CLOSE"
    if reason == "broker_manual_close" or oanda == "MARKET_ORDER_TRADE_CLOSE":
        return "MANUAL"
    if reason in ("reconcile", "reconciliation"):
        return "RECONCILIATION"
    return analysis_class or "UNKNOWN"


def main() -> None:
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    trades = analysis["trades"]
    dump = json.loads(DUMP.read_text(encoding="utf-8"))
    dump_by_id = {int(t["id"]): t for t in dump.get("trades") or [] if t.get("id") is not None}
    orders = dump.get("exec_orders") or []
    by_broker = {str(o.get("broker_order_id")): o for o in orders if o.get("broker_order_id")}

    for r in trades:
        raw = dump_by_id.get(int(r["id"])) if r.get("id") is not None else None
        diag = (raw or {}).get("diagnostics") or {}
        r["dump_exit_reason"] = diag.get("exit_reason") if isinstance(diag, dict) else None
        r["dump_oanda_reason"] = diag.get("oanda_reason") if isinstance(diag, dict) else None
        r["dump_oanda_type"] = diag.get("oanda_transaction_type") if isinstance(diag, dict) else None
        r["audit_class"] = reclass(diag if isinstance(diag, dict) else {}, r.get("exit_class"))
        bid = str(r.get("broker_trade_id") or "")
        order = by_broker.get(bid) or {}
        created = _ts(order.get("created_at"))
        filled = _ts(order.get("filled_at"))
        if created and filled:
            r["order_latency_sec"] = (filled - created).total_seconds()
        else:
            r["order_latency_sec"] = None
        entry = _ts(r.get("entry_ts"))
        if entry is not None:
            r["entry_sec_into_m5"] = (
                entry.minute % 5
            ) * 60 + entry.second + entry.microsecond / 1e6
        else:
            r["entry_sec_into_m5"] = None
        pre5 = _f((r.get("pre_move_pips") or {}).get("5"))
        r["pre5"] = pre5
        if pre5 is None:
            r["momentum_align"] = "UNKNOWN"
        elif pre5 > 0:
            r["momentum_align"] = "ALIGNED"
        elif pre5 < 0:
            r["momentum_align"] = "OPPOSITE"
        else:
            r["momentum_align"] = "FLAT"
        fwd5 = (r.get("forward") or {}).get("5") or {}
        r["fwd5_r"] = _f(fwd5.get("r")) if isinstance(fwd5, dict) else None
        r["fwd5_pips"] = _f(fwd5.get("pips")) if isinstance(fwd5, dict) else None
        hold = _f(r.get("hold_sec"))
        r["closed_by_5m"] = bool(hold is not None and hold <= 300)
        r["closed_4_6m"] = bool(hold is not None and 240 <= hold <= 360)

    scored = [r for r in trades if r.get("exit_class") in SCORED]
    sl_rows = [r for r in scored if r.get("exit_class") == "BROKER_STOP_LOSS"]
    closed_5 = [r for r in scored if r["closed_by_5m"]]
    closed_4_6 = [r for r in trades if r["closed_4_6m"]]

    # Hold-time distribution
    holds = [_f(r.get("hold_sec")) for r in scored]
    holds = [h for h in holds if h is not None]
    bins = [
        (0, 60, "0-60s"),
        (60, 120, "60-120s"),
        (120, 180, "120-180s"),
        (180, 240, "180-240s"),
        (240, 300, "240-300s"),
        (300, 360, "300-360s"),
        (360, 600, "360-600s"),
        (600, 1800, "10-30m"),
        (1800, 1e12, ">30m"),
    ]
    hold_bins = []
    for lo, hi, name in bins:
        n = sum(1 for h in holds if lo <= h < hi)
        hold_bins.append({"bin": name, "n": n, "pct": pct(n, len(holds))})
    clusters = []
    for mark in ROUND_MARKS:
        n = sum(1 for h in holds if abs(h - mark) <= ROUND_WINDOW)
        clusters.append(
            {
                "mark_sec": mark,
                "window_sec": ROUND_WINDOW,
                "n": n,
                "pct": pct(n, len(holds)),
            }
        )
    exact_300 = sum(1 for h in holds if abs(h - 300) <= 2)

    # First-5m path: M1 unavailable. Use 5m executable forward + trades that died inside 5m.
    immediate = [r for r in sl_rows if _f(r.get("mfe_r")) is not None and r["mfe_r"] < 0.25]
    reversed_ = [
        r
        for r in sl_rows
        if _f(r.get("mfe_r")) is not None and r["mfe_r"] >= 0.5
    ]
    mixed = [
        r
        for r in sl_rows
        if _f(r.get("mfe_r")) is not None and 0.25 <= r["mfe_r"] < 0.5
    ]
    sl_closed_5 = [r for r in sl_rows if r["closed_by_5m"]]

    # First-5m MAE vs SL for trades that closed by 5m (path is the whole trade)
    sl_vs_mae_5 = []
    for r in sl_closed_5:
        sl_p = _f(r.get("sl_pips"))
        mae = _f(r.get("mae_pips"))
        mfe = _f(r.get("mfe_pips"))
        spr = _f(r.get("spread_pips"))
        sl_vs_mae_5.append(
            {
                "id": r["id"],
                "symbol": r["symbol"],
                "side": r["side"],
                "hold_sec": round(r["hold_sec"], 1) if r.get("hold_sec") else None,
                "sl_pips": sl_p,
                "mae_pips": mae,
                "mfe_pips": mfe,
                "spread_pips": spr,
                "sl_minus_spread": None if sl_p is None or spr is None else round(sl_p - spr, 3),
                "mae_over_sl": None if sl_p in (None, 0) or mae is None else round(mae / sl_p, 3),
            }
        )

    # SL geometry
    sl_small = [r for r in scored if _f(r.get("sl_pips")) is not None and r["sl_pips"] < 2.0]
    sl_near_spread = [
        r
        for r in scored
        if _f(r.get("stop_over_spread")) is not None and r["stop_over_spread"] < 1.5
    ]
    sl_inside_spread = [
        r
        for r in scored
        if _f(r.get("sl_pips")) is not None
        and _f(r.get("spread_pips")) is not None
        and r["sl_pips"] <= r["spread_pips"]
    ]
    by_side_sl = {}
    for side in ("BUY", "SELL"):
        sub = [r for r in scored if r.get("side") == side]
        by_side_sl[side] = {
            "n": len(sub),
            "sl_pips": summarize([_f(r.get("sl_pips")) for r in sub]),
            "stop_over_atr": summarize([_f(r.get("stop_over_atr")) for r in sub]),
            "stop_over_spread": summarize([_f(r.get("stop_over_spread")) for r in sub]),
            "spread_pips": summarize([_f(r.get("spread_pips")) for r in sub]),
        }
    by_symbol_sl = {}
    for sym in sorted({r["symbol"] for r in scored}):
        sub = [r for r in scored if r["symbol"] == sym]
        by_symbol_sl[sym] = {
            "n": len(sub),
            "sl_pips": summarize([_f(r.get("sl_pips")) for r in sub]),
            "atr_pips": summarize([_f(r.get("atr_pips")) for r in sub]),
            "stop_over_atr": summarize([_f(r.get("stop_over_atr")) for r in sub]),
            "spread_pips": summarize([_f(r.get("spread_pips")) for r in sub]),
            "stop_over_spread": summarize([_f(r.get("stop_over_spread")) for r in sub]),
            "initial_r": summarize([_f(r.get("initial_r")) for r in sub]),
        }

    # 4-6 minute individual
    four_six = []
    for r in sorted(closed_4_6, key=lambda x: x.get("hold_sec") or 0):
        four_six.append(
            {
                "id": r["id"],
                "symbol": r["symbol"],
                "side": r["side"],
                "strategy": r["strategy"],
                "hold_sec": round(r["hold_sec"], 1) if r.get("hold_sec") else None,
                "analysis_class": r.get("exit_class"),
                "audit_class": r.get("audit_class"),
                "oanda_reason": r.get("oanda_reason") or r.get("dump_oanda_reason"),
                "dump_exit_reason": r.get("dump_exit_reason"),
                "dump_oanda_type": r.get("dump_oanda_type"),
                "realised_r": r.get("realised_r"),
                "mfe_r": r.get("mfe_r"),
                "mae_r": r.get("mae_r"),
                "sl_pips": r.get("sl_pips"),
                "fwd5_r": r.get("fwd5_r"),
            }
        )

    # Opposite-signed momentum
    mom = {}
    for label in ("ALIGNED", "OPPOSITE", "FLAT", "UNKNOWN"):
        sub = [r for r in scored if r["momentum_align"] == label]
        mom[label] = {
            **expectancy_block(sub),
            "5m_hit": hit(sub, 5),
            "15m_hit": hit(sub, 15),
            "60m_hit": hit(sub, 60),
            "mfe_r": summarize([_f(r.get("mfe_r")) for r in sub]),
            "mae_r": summarize([_f(r.get("mae_r")) for r in sub]),
            "closed_by_5m": sum(1 for r in sub if r["closed_by_5m"]),
            "sl_share": pct(sum(1 for r in sub if r["exit_class"] == "BROKER_STOP_LOSS"), len(sub)),
        }

    # Signal lateness: already moved our way, then 5m reverse
    late_chase = [
        r
        for r in scored
        if r["momentum_align"] == "ALIGNED"
        and r.get("fwd5_r") is not None
        and r["fwd5_r"] < 0
    ]
    late_ok = [
        r
        for r in scored
        if r["momentum_align"] == "ALIGNED"
        and r.get("fwd5_r") is not None
        and r["fwd5_r"] > 0
    ]
    fade_then_work = [
        r
        for r in scored
        if r["momentum_align"] == "OPPOSITE"
        and r.get("fwd5_r") is not None
        and r["fwd5_r"] > 0
    ]
    fade_then_fail = [
        r
        for r in scored
        if r["momentum_align"] == "OPPOSITE"
        and r.get("fwd5_r") is not None
        and r["fwd5_r"] < 0
    ]

    pre_vs_post = {}
    for side in ("BUY", "SELL", "ALL"):
        sub = scored if side == "ALL" else [r for r in scored if r.get("side") == side]
        pre_vs_post[side] = {
            "n": len(sub),
            "pre5": summarize([r.get("pre5") for r in sub]),
            "pre15": summarize([_f((r.get("pre_move_pips") or {}).get("15")) for r in sub]),
            "pre30": summarize([_f((r.get("pre_move_pips") or {}).get("30")) for r in sub]),
            "fwd5_r": fwd_r(sub, 5),
            "fwd15_r": fwd_r(sub, 15),
            "fwd30_r": fwd_r(sub, 30),
            "fwd60_r": fwd_r(sub, 60),
            "aligned_n": sum(1 for r in sub if r["momentum_align"] == "ALIGNED"),
            "opposite_n": sum(1 for r in sub if r["momentum_align"] == "OPPOSITE"),
            "chase_then_5m_loss": sum(
                1
                for r in sub
                if r["momentum_align"] == "ALIGNED"
                and r.get("fwd5_r") is not None
                and r["fwd5_r"] < 0
            ),
        }
    pre_by_symbol = {}
    for sym in sorted({r["symbol"] for r in scored}):
        sub = [r for r in scored if r["symbol"] == sym]
        pre_by_symbol[sym] = {
            "n": len(sub),
            "pre5": summarize([r.get("pre5") for r in sub]),
            "fwd5_r": fwd_r(sub, 5),
            "fwd5_hit": hit(sub, 5),
            "aligned_n": sum(1 for r in sub if r["momentum_align"] == "ALIGNED"),
            "opposite_n": sum(1 for r in sub if r["momentum_align"] == "OPPOSITE"),
        }

    # First-5m failure by symbol/strategy: closed_by_5m losing, or 5m dir miss
    def fail5(rows):
        n = len(rows)
        closed_lose = [
            r
            for r in rows
            if r["closed_by_5m"] and _f(r.get("realised_r")) is not None and r["realised_r"] < 0
        ]
        dir_miss = [
            r
            for r in rows
            if (r.get("dir_correct") or {}).get("5") is False
            or (r.get("dir_correct") or {}).get(5) is False
        ]
        return {
            "n": n,
            "closed_by_5m": sum(1 for r in rows if r["closed_by_5m"]),
            "closed_by_5m_loss": len(closed_lose),
            "closed_by_5m_loss_pct": pct(len(closed_lose), n),
            "fwd5_miss": len(dir_miss),
            "fwd5_miss_pct": pct(len(dir_miss), n),
            "fwd5_hit": hit(rows, 5),
            "mean_r": expectancy_block(rows).get("mean_r"),
        }

    by_symbol_5 = {sym: fail5([r for r in scored if r["symbol"] == sym]) for sym in sorted({r["symbol"] for r in scored})}
    by_strategy_5 = {
        st: fail5([r for r in scored if r["strategy"] == st])
        for st in sorted({r.get("strategy") or "unknown" for r in scored})
    }
    by_side_5 = {side: fail5([r for r in scored if r["side"] == side]) for side in ("BUY", "SELL")}

    # Entry timing within M5
    into = [_f(r.get("entry_sec_into_m5")) for r in scored]
    into = [x for x in into if x is not None]
    into_bins = [
        (0, 15, "0-15s after M5"),
        (15, 60, "15-60s"),
        (60, 120, "60-120s"),
        (120, 180, "120-180s"),
        (180, 240, "180-240s"),
        (240, 300, "240-300s (late in forming bar)"),
    ]
    entry_bins = []
    for lo, hi, name in into_bins:
        n = sum(1 for x in into if lo <= x < hi)
        entry_bins.append({"bin": name, "n": n, "pct": pct(n, len(into))})

    # V2 shadow
    shadow_n = 0
    shadow_rl = Counter()
    shadow_agree = 0
    shadow_veto = 0
    shadow_first = None
    shadow_last = None
    if SHADOW.exists():
        with SHADOW.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                shadow_n += 1
                ts = rec.get("timestamp_utc")
                if shadow_first is None:
                    shadow_first = ts
                shadow_last = ts
                rl = rec.get("rl") or {}
                shadow_rl[str(rl.get("action") or "none")] += 1
                if rl.get("agree"):
                    shadow_agree += 1
                if rl.get("veto"):
                    shadow_veto += 1
    last_entry = max((_ts(r["entry_ts"]) for r in trades if r.get("entry_ts")), default=None)
    first_shadow = _ts(shadow_first)
    shadow_overlap = bool(
        first_shadow and last_entry and first_shadow <= last_entry
    )

    # Class counts
    class_counts = Counter(r.get("audit_class") for r in trades)
    analysis_counts = Counter(r.get("exit_class") for r in trades)

    # 5m forward for all scored (uncensored direction)
    # Immediate adverse among SL closed by 5m
    sl5_mfe0 = sum(1 for r in sl_closed_5 if _f(r.get("mfe_r")) is not None and r["mfe_r"] <= 0.05)

    out = {
        "source": {
            "analysis": str(ANALYSIS.relative_to(ROOT)),
            "dump": str(DUMP.relative_to(ROOT)),
            "m1_available": False,
            "finest_path": "M5 executable bid/ask close + bot tick MFE/MAE at exit",
            "n_trades": len(trades),
            "n_scored": len(scored),
            "boundary": analysis.get("boundary_utc"),
        },
        "hold": {
            "scored": summarize(holds),
            "bins": hold_bins,
            "round_clusters_pm15s": clusters,
            "exact_300_pm2s": exact_300,
            "closed_by_5m": len(closed_5),
            "closed_by_5m_pct": pct(len(closed_5), len(scored)),
            "closed_4_6m": len(closed_4_6),
        },
        "first_5m": {
            "note": "M1 not available. 0-1/1-2/2-3/3-4/4-5 minute path cannot be measured. Use hold bins + 5m executable forward + bot MFE/MAE.",
            "scored_5m_forward_r": fwd_r(scored, 5),
            "scored_5m_hit": hit(scored, 5),
            "closed_inside_5m": {
                **expectancy_block(closed_5),
                "by_class": dict(Counter(r["exit_class"] for r in closed_5)),
                "mean_mfe_r": summarize([_f(r.get("mfe_r")) for r in closed_5]),
                "mean_mae_r": summarize([_f(r.get("mae_r")) for r in closed_5]),
            },
            "sl_mfe_buckets": {
                "immediate_mfe_lt_0.25R": len(immediate),
                "mixed_0.25_0.5R": len(mixed),
                "initial_profit_then_sl_mfe_ge_0.5R": len(reversed_),
                "sl_n": len(sl_rows),
            },
            "sl_closed_inside_5m": {
                "n": len(sl_closed_5),
                "mfe_near_zero": sl5_mfe0,
                "mean_mfe_r": summarize([_f(r.get("mfe_r")) for r in sl_closed_5]),
                "mean_mae_r": summarize([_f(r.get("mae_r")) for r in sl_closed_5]),
            },
            "losing_path_class": (
                "immediate adverse movement"
                if len(immediate) >= 0.5 * max(1, len(sl_rows))
                else "mixed"
            ),
        },
        "sl_geometry": {
            "all_scored": {
                "sl_pips": summarize([_f(r.get("sl_pips")) for r in scored]),
                "atr_pips": summarize([_f(r.get("atr_pips")) for r in scored]),
                "stop_over_atr": summarize([_f(r.get("stop_over_atr")) for r in scored]),
                "spread_pips": summarize([_f(r.get("spread_pips")) for r in scored]),
                "stop_over_spread": summarize([_f(r.get("stop_over_spread")) for r in scored]),
                "initial_r": summarize([_f(r.get("initial_r")) for r in scored]),
            },
            "sl_pips_under_2": len(sl_small),
            "sl_inside_or_equal_spread": len(sl_inside_spread),
            "stop_over_spread_lt_1.5": len(sl_near_spread),
            "by_side": by_side_sl,
            "by_symbol": by_symbol_sl,
            "sl_closed_5m_detail_n": len(sl_vs_mae_5),
        },
        "exits": {
            "analysis_class": dict(analysis_counts),
            "audit_class": dict(class_counts),
            "four_to_six_min": four_six,
        },
        "entry_timing": {
            "order_latency_sec": summarize([_f(r.get("order_latency_sec")) for r in scored]),
            "sec_into_m5": summarize(into),
            "bins": entry_bins,
        },
        "signal_lag": {
            "pre10_available": False,
            "plus_1m_available": False,
            "plus_10m_available": False,
            "by_side": pre_vs_post,
            "by_symbol": pre_by_symbol,
            "chase_then_5m_loss_n": len(late_chase),
            "chase_then_5m_win_n": len(late_ok),
            "opposite_then_5m_win_n": len(fade_then_work),
            "opposite_then_5m_loss_n": len(fade_then_fail),
        },
        "opposite_momentum": mom,
        "concentration": {
            "by_symbol": by_symbol_5,
            "by_strategy": by_strategy_5,
            "by_side": by_side_5,
        },
        "v2_shadow": {
            "n": shadow_n,
            "first": shadow_first,
            "last": shadow_last,
            "rl_actions": dict(shadow_rl),
            "agree": shadow_agree,
            "veto": shadow_veto,
            "overlaps_corrected_live_sample": shadow_overlap,
            "last_sample_entry": last_entry.isoformat() if last_entry else None,
        },
    }
    OUT.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print("wrote", OUT)
    print("scored", len(scored), "closed_5m", len(closed_5), "4-6m", len(closed_4_6))
    print("hold bins", hold_bins)
    print("clusters", clusters)
    print("exact300", exact_300)
    print("audit class", dict(class_counts))
    print("mom", {k: v["n"] for k, v in mom.items()})
    print("5m hit", hit(scored, 5), "fwd5", fwd_r(scored, 5))
    print("shadow", shadow_n, "overlap", shadow_overlap)
    print("entry into m5", summarize(into))
    print("4-6m ids", [x["id"] for x in four_six])


if __name__ == "__main__":
    main()

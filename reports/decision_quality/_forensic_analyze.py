"""Read-only reconstruction of the 20-21 Sep 2026 OANDA window. No broker writes."""
from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TX_PATH = Path(__file__).resolve().parent / "_oanda_tx_20_21.json"
OUT = Path(__file__).resolve().parent / "_forensic_summary.json"

# Count-matched window (external 148 CLIENT_ORDER / 47 SL / 7 TP / 61 closeout).
# External text said 20:21; counts and the AUD 0.71176 fill match 21:21 UTC.
WIN_START = "2026-09-20T20:05:00.000000000Z"
WIN_END = "2026-09-21T21:21:59.999999999Z"

# Proven first new-management container start (BST 10:40:11 = UTC 09:40:11).
NEW_MGMT_START = datetime(2026, 9, 21, 9, 40, 11, tzinfo=timezone.utc)
# Later restart that added broker-exit accounting (still new management).
BROKER_EXIT_START = datetime(2026, 9, 21, 11, 41, 55, tzinfo=timezone.utc)

KNOWN_OLD_BUG = {"1589", "1597", "1621", "1629"}
REJ_REASONS = {
    "LOSING_TAKE_PROFIT",
    "STOP_LOSS_ON_FILL_LOSS",
    "TAKE_PROFIT_ON_FILL_LOSS",
}
PIP = {
    "EUR_USD": 0.0001,
    "GBP_USD": 0.0001,
    "AUD_USD": 0.0001,
    "USD_CAD": 0.0001,
    "USD_CHF": 0.0001,
    "USD_JPY": 0.01,
}


def parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    s = str(raw).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    # trim nanos to micros
    if "." in s:
        head, rest = s.split(".", 1)
        frac = ""
        tz = "+00:00"
        for i, ch in enumerate(rest):
            if ch.isdigit():
                frac += ch
            else:
                tz = rest[i:]
                break
        frac = (frac + "000000")[:6]
        s = f"{head}.{frac}{tz}"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fnum(v, default=None):
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def pctile(xs, p):
    if not xs:
        return None
    ys = sorted(xs)
    if len(ys) == 1:
        return ys[0]
    k = (len(ys) - 1) * p
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return ys[lo]
    return ys[lo] * (hi - k) + ys[hi] * (k - lo)


def dist_stats(xs):
    xs = [x for x in xs if x is not None and math.isfinite(x)]
    if not xs:
        return {}
    return {
        "n": len(xs),
        "min": min(xs),
        "p01": pctile(xs, 0.01),
        "p05": pctile(xs, 0.05),
        "p25": pctile(xs, 0.25),
        "median": pctile(xs, 0.50),
        "p75": pctile(xs, 0.75),
        "p95": pctile(xs, 0.95),
        "p99": pctile(xs, 0.99),
        "max": max(xs),
        "mean": statistics.fmean(xs),
    }


def classify_build(ts: datetime | None) -> str:
    if ts is None:
        return "UNKNOWN"
    if ts < NEW_MGMT_START:
        return "OLD_FAULTY_BUILD"
    return "NEW_FIXED_BUILD"


def side_from_units(u: float | None) -> str | None:
    if u is None:
        return None
    if u > 0:
        return "BUY"
    if u < 0:
        return "SELL"
    return None


def pip_size(sym: str) -> float:
    return PIP.get(sym, 0.0001)


def r_ratio(entry: float | None, sl: float | None, tp: float | None, side: str | None):
    if entry is None or sl is None or tp is None or not side:
        return None
    if side == "BUY":
        risk = entry - sl
        reward = tp - entry
    else:
        risk = sl - entry
        reward = entry - tp
    if risk is None or abs(risk) < 1e-12:
        return None
    return reward / risk


def orientation_ok(entry, sl, tp, side) -> bool | None:
    if None in (entry, sl, tp) or not side:
        return None
    if side == "BUY":
        return sl < entry < tp
    return tp < entry < sl


def hold_bucket(sec: float | None) -> str:
    if sec is None:
        return "unknown"
    if sec <= 30:
        return "0-30s"
    if sec <= 45:
        return "31-45s"
    if sec <= 90:
        return "46-90s"
    if sec <= 120:
        return "91-120s"
    if sec <= 300:
        return "2-5m"
    if sec <= 900:
        return "5-15m"
    return "15m+"


def rapid_bucket(sec: float | None) -> list[str]:
    if sec is None:
        return []
    labels = []
    for lim, name in (
        (15, "15s"),
        (30, "30s"),
        (60, "60s"),
        (90, "90s"),
        (120, "2m"),
        (300, "5m"),
        (600, "10m"),
        (1800, "30m"),
    ):
        if sec <= lim:
            labels.append(f"<={name}")
    if sec >= 3600:
        labels.append(">=60m")
    return labels


def main() -> None:
    raw = json.loads(TX_PATH.read_text(encoding="utf-8"))
    all_txs = raw["transactions"]
    by_id = {str(t.get("id")): t for t in all_txs}

    window = [
        t
        for t in all_txs
        if WIN_START <= str(t.get("time") or "") <= WIN_END
    ]
    window.sort(key=lambda t: (t.get("time") or "", int(t.get("id") or 0)))

    type_reason = Counter((t.get("type"), t.get("reason")) for t in window)
    types = Counter(t.get("type") for t in window)

    client_orders = [
        t
        for t in window
        if t.get("type") == "MARKET_ORDER" and t.get("reason") == "CLIENT_ORDER"
    ]
    entry_fills = []
    closing_fills = []
    for t in window:
        if t.get("type") != "ORDER_FILL":
            continue
        reason = t.get("reason")
        if reason == "MARKET_ORDER" and t.get("tradeOpened"):
            entry_fills.append(t)
        elif reason in {
            "STOP_LOSS_ORDER",
            "TAKE_PROFIT_ORDER",
            "MARKET_ORDER_POSITION_CLOSEOUT",
            "MARKET_ORDER_TRADE_CLOSE",
        } or t.get("tradesClosed"):
            closing_fills.append(t)

    # Reconstruct trades from entry fills + later closing fills.
    trades: dict[str, dict] = {}
    for t in entry_fills:
        opened = t.get("tradeOpened") or {}
        tid = str(opened.get("tradeID") or t.get("id"))
        units = fnum(opened.get("units") or t.get("units"))
        inst = t.get("instrument")
        side = side_from_units(units)
        batch = str(t.get("batchID") or "")
        mo = by_id.get(batch) or by_id.get(str(t.get("orderID") or ""))
        sl = tp = None
        if mo:
            sl = fnum((mo.get("stopLossOnFill") or {}).get("price"))
            tp = fnum((mo.get("takeProfitOnFill") or {}).get("price"))
        # ON_FILL SL/TP in same batch
        for sib in all_txs:
            if str(sib.get("batchID")) != batch:
                continue
            if sib.get("type") == "STOP_LOSS_ORDER" and sl is None:
                sl = fnum(sib.get("price"))
            if sib.get("type") == "TAKE_PROFIT_ORDER" and tp is None:
                tp = fnum(sib.get("price"))
        full = t.get("fullPrice") or {}
        bid = None
        ask = None
        bids = full.get("bids") or []
        asks = full.get("asks") or []
        if bids and isinstance(bids[0], dict):
            bid = fnum(bids[0].get("price"))
        if asks and isinstance(asks[0], dict):
            ask = fnum(asks[0].get("price"))
        cob = fnum(full.get("closeoutBid"))
        coa = fnum(full.get("closeoutAsk"))
        fill = fnum(t.get("price") or opened.get("price"))
        et = parse_ts(t.get("time"))
        # Infer decision mid from 2R construction if SL/TP present
        inferred_mid = None
        if sl is not None and tp is not None:
            inferred_mid = (2.0 * sl + tp) / 3.0 if side == "BUY" else (2.0 * sl + tp) / 3.0
            # SELL: SL=mid+sl_d, TP=mid-2*sl_d → 2*SL+TP = 2mid+2sld + mid - 2sld = 3mid → same formula
            inferred_mid = (2.0 * sl + tp) / 3.0
        trades[tid] = {
            "trade_id": tid,
            "symbol": inst,
            "side": side,
            "units": abs(units) if units is not None else None,
            "signed_units": units,
            "entry_tx": str(t.get("id")),
            "entry_order_id": str(t.get("orderID") or ""),
            "entry_batch": batch,
            "client_order_id": t.get("clientOrderID") or (mo or {}).get("clientExtensions", {}).get("id")
            if mo
            else t.get("clientOrderID"),
            "entry_time": t.get("time"),
            "entry_ts": et.isoformat() if et else None,
            "entry_price": fill,
            "submitted_sl": sl,
            "submitted_tp": tp,
            "bid": bid,
            "ask": ask,
            "closeout_bid": cob,
            "closeout_ask": coa,
            "half_spread_cost_entry": fnum(t.get("halfSpreadCost")),
            "spread": (ask - bid) if bid is not None and ask is not None else None,
            "inferred_mid": inferred_mid,
            "decision_r": r_ratio(inferred_mid, sl, tp, side),
            "fill_r": r_ratio(fill, sl, tp, side),
            "decision_orient_ok": orientation_ok(inferred_mid, sl, tp, side),
            "fill_orient_ok": orientation_ok(fill, sl, tp, side),
            "entry_build": classify_build(et),
            "pl": None,
        }

    for t in closing_fills:
        closed = t.get("tradesClosed") or []
        if not closed and t.get("tradeReduced"):
            closed = [t.get("tradeReduced")]
        reason = t.get("reason")
        xt = parse_ts(t.get("time"))
        for c in closed or [{}]:
            tid = str(c.get("tradeID") or "")
            rec = trades.get(tid)
            if rec is None:
                # close without entry in window
                rec = {
                    "trade_id": tid,
                    "symbol": t.get("instrument"),
                    "side": None,
                    "entry_tx": None,
                    "orphan_close": True,
                }
                trades[tid] = rec
            rec["exit_tx"] = str(t.get("id"))
            rec["exit_time"] = t.get("time")
            rec["exit_ts"] = xt.isoformat() if xt else None
            rec["exit_price"] = fnum(c.get("price") or t.get("price"))
            rec["realized_pl"] = fnum(c.get("realizedPL") or t.get("pl"))
            rec["half_spread_cost_exit"] = fnum(t.get("halfSpreadCost"))
            rec["oanda_type"] = t.get("type")
            rec["oanda_reason"] = reason
            rec["exit_build"] = classify_build(xt)
            et = parse_ts(rec.get("entry_time"))
            if et and xt:
                rec["hold_sec"] = (xt - et).total_seconds()
            else:
                rec["hold_sec"] = None
            if rec.get("entry_build") == "OLD_FAULTY_BUILD" and rec.get("exit_build") == "NEW_FIXED_BUILD":
                rec["build"] = "BOUNDARY_AMBIGUOUS"
            elif rec.get("entry_build"):
                rec["build"] = rec["entry_build"]
            else:
                rec["build"] = rec.get("exit_build") or "UNKNOWN"
            # classification
            hold = rec.get("hold_sec")
            if reason == "STOP_LOSS_ORDER":
                rec["class"] = "BROKER_STOP_LOSS"
            elif reason == "TAKE_PROFIT_ORDER":
                rec["class"] = "BROKER_TAKE_PROFIT"
            elif reason == "MARKET_ORDER_POSITION_CLOSEOUT":
                if tid in KNOWN_OLD_BUG:
                    rec["class"] = (
                        "BOT_PROFIT_PROTECTION_OLD_BUG"
                        if tid != "1629"
                        else "BOT_LOCAL_SLTP_OLD_BUG"
                    )
                elif rec.get("build") == "OLD_FAULTY_BUILD" and hold is not None and 46 <= hold <= 90:
                    rec["class"] = "BOT_PROFIT_PROTECTION_OLD_BUG"  # provisional; refined by PG
                    rec["class_provisional"] = True
                elif rec.get("build") == "NEW_FIXED_BUILD":
                    rec["class"] = "OTHER_BOT_CLOSE"  # refined by logs/PG
                else:
                    rec["class"] = "OTHER_BOT_CLOSE"
            elif reason == "MARKET_ORDER_TRADE_CLOSE":
                rec["class"] = "OTHER_BROKER_CLOSE"
            else:
                rec["class"] = "UNKNOWN"
            if tid in KNOWN_OLD_BUG:
                rec["known_old_bug"] = True

    # Rejections: ORDER_CANCEL of entry-related reasons
    rejections = []
    for t in window:
        if t.get("type") != "ORDER_CANCEL" or t.get("reason") not in REJ_REASONS:
            continue
        oid = str(t.get("orderID") or "")
        mo = by_id.get(oid)
        # sometimes cancel references the market order that failed to attach
        sl = tp = None
        inst = None
        units = None
        side = None
        bid = ask = None
        fill = None
        if mo:
            inst = mo.get("instrument")
            units = fnum(mo.get("units"))
            side = side_from_units(units)
            sl = fnum((mo.get("stopLossOnFill") or {}).get("price"))
            tp = fnum((mo.get("takeProfitOnFill") or {}).get("price"))
        # related fill in same batch
        batch = str(t.get("batchID") or (mo or {}).get("batchID") or "")
        fill_tx = None
        for sib in all_txs:
            if str(sib.get("batchID")) != batch:
                continue
            if sib.get("type") == "ORDER_FILL":
                fill_tx = sib
                fill = fnum(sib.get("price"))
                full = sib.get("fullPrice") or {}
                bids = full.get("bids") or []
                asks = full.get("asks") or []
                if bids:
                    bid = fnum(bids[0].get("price"))
                if asks:
                    ask = fnum(asks[0].get("price"))
                if not inst:
                    inst = sib.get("instrument")
        inferred_mid = (2.0 * sl + tp) / 3.0 if sl is not None and tp is not None else None
        rt = parse_ts(t.get("time"))
        rejections.append(
            {
                "cancel_id": str(t.get("id")),
                "order_id": oid,
                "batch": batch,
                "time": t.get("time"),
                "reason": t.get("reason"),
                "symbol": inst,
                "side": side,
                "units": units,
                "submitted_sl": sl,
                "submitted_tp": tp,
                "fill": fill,
                "bid": bid,
                "ask": ask,
                "spread": (ask - bid) if bid is not None and ask is not None else None,
                "inferred_mid": inferred_mid,
                "decision_r": r_ratio(inferred_mid, sl, tp, side),
                "fill_r": r_ratio(fill, sl, tp, side) if fill else None,
                "decision_orient_ok": orientation_ok(inferred_mid, sl, tp, side),
                "fill_orient_ok": orientation_ok(fill, sl, tp, side) if fill else None,
                "had_fill": fill_tx is not None,
                "fill_opened_trade": bool((fill_tx or {}).get("tradeOpened")),
                "build": classify_build(rt),
                "client_order_id": t.get("clientOrderID")
                or ((mo or {}).get("clientExtensions") or {}).get("id"),
            }
        )

    completed = [tr for tr in trades.values() if tr.get("exit_tx")]
    opened = [tr for tr in trades.values() if tr.get("entry_tx")]

    def pl_stats(rows):
        pls = [r["realized_pl"] for r in rows if r.get("realized_pl") is not None]
        wins = [p for p in pls if p > 0]
        losses = [p for p in pls if p < 0]
        zeros = [p for p in pls if p == 0]
        gp = sum(wins)
        gl = abs(sum(losses))
        return {
            "n": len(rows),
            "wins": len(wins),
            "losses": len(losses),
            "zeros": len(zeros),
            "total_pl": sum(pls) if pls else 0.0,
            "avg_win": statistics.fmean(wins) if wins else None,
            "avg_loss": statistics.fmean(losses) if losses else None,
            "profit_factor": (gp / gl) if gl > 0 else None,
            "win_rate": (len(wins) / len([p for p in pls if p != 0])) if any(p != 0 for p in pls) else None,
        }

    # halfSpreadCost over ORDER_FILL in window
    hsc = [fnum(t.get("halfSpreadCost"), 0.0) or 0.0 for t in window if t.get("type") == "ORDER_FILL"]

    # pair closing PL
    pair_pl = defaultdict(float)
    pair_n = Counter()
    for tr in completed:
        pair_pl[tr.get("symbol")] += float(tr.get("realized_pl") or 0)
        pair_n[tr.get("symbol")] += 1

    # R buckets
    def r_buckets(key):
        vals = [tr.get(key) for tr in opened if tr.get(key) is not None]
        cuts = [0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75]
        out = {f"below_{c}": sum(1 for v in vals if v < c) for c in cuts}
        out["near_2"] = sum(1 for v in vals if 1.8 <= v <= 2.2)
        out["invalid_or_neg"] = sum(1 for v in vals if v <= 0)
        out["stats"] = dist_stats(vals)
        return out

    # pair x direction
    pair_dir = {}
    for tr in opened:
        k = f"{tr.get('symbol')} {tr.get('side')}"
        pair_dir.setdefault(k, {"entries": 0, "exits": [], "sl": 0, "tp": 0, "bot": 0, "fill_r": [], "spread_tp": []})
        pair_dir[k]["entries"] += 1
        if tr.get("exit_tx"):
            pair_dir[k]["exits"].append(tr)
            if tr.get("oanda_reason") == "STOP_LOSS_ORDER":
                pair_dir[k]["sl"] += 1
            elif tr.get("oanda_reason") == "TAKE_PROFIT_ORDER":
                pair_dir[k]["tp"] += 1
            elif "POSITION_CLOSEOUT" in str(tr.get("oanda_reason") or ""):
                pair_dir[k]["bot"] += 1
        if tr.get("fill_r") is not None:
            pair_dir[k]["fill_r"].append(tr["fill_r"])
        if tr.get("spread") is not None and tr.get("submitted_tp") is not None and tr.get("entry_price") is not None:
            tp_dist = abs(tr["submitted_tp"] - tr["entry_price"])
            if tp_dist > 0:
                pair_dir[k]["spread_tp"].append(tr["spread"] / tp_dist)

    pair_dir_out = {}
    for k, v in sorted(pair_dir.items()):
        st = pl_stats(v["exits"])
        holds = [r.get("hold_sec") for r in v["exits"] if r.get("hold_sec") is not None]
        pair_dir_out[k] = {
            **st,
            "filled_entries": v["entries"],
            "stop_loss": v["sl"],
            "take_profit": v["tp"],
            "bot_close": v["bot"],
            "median_hold": pctile(holds, 0.5) if holds else None,
            "median_fill_r": pctile(v["fill_r"], 0.5) if v["fill_r"] else None,
            "median_spread_tp": pctile(v["spread_tp"], 0.5) if v["spread_tp"] else None,
        }

    # closeout attribution
    closeouts = [tr for tr in completed if tr.get("oanda_reason") == "MARKET_ORDER_POSITION_CLOSEOUT"]
    closeout_by_class = defaultdict(list)
    for tr in closeouts:
        closeout_by_class[tr.get("class") or "UNKNOWN"].append(tr)

    def group_report(rows):
        holds = [r.get("hold_sec") for r in rows if r.get("hold_sec") is not None]
        buckets = Counter(hold_bucket(h) for h in holds)
        return {
            **pl_stats(rows),
            "avg_pl": statistics.fmean([r["realized_pl"] for r in rows if r.get("realized_pl") is not None])
            if rows
            else None,
            "median_hold": pctile(holds, 0.5) if holds else None,
            "hold_buckets": dict(buckets),
        }

    # old vs new
    def by_build(build):
        ents = [tr for tr in opened if tr.get("entry_build") == build]
        exs = [tr for tr in completed if tr.get("build") == build]
        sls = [tr for tr in exs if tr.get("oanda_reason") == "STOP_LOSS_ORDER"]
        tps = [tr for tr in exs if tr.get("oanda_reason") == "TAKE_PROFIT_ORDER"]
        posc = [tr for tr in exs if tr.get("oanda_reason") == "MARKET_ORDER_POSITION_CLOSEOUT"]
        trc = [tr for tr in exs if tr.get("oanda_reason") == "MARKET_ORDER_TRADE_CLOSE"]
        rejs = [r for r in rejections if r.get("build") == build]
        holds = [tr.get("hold_sec") for tr in exs if tr.get("hold_sec") is not None]
        fill_rs = [tr.get("fill_r") for tr in ents if tr.get("fill_r") is not None]
        dec_rs = [tr.get("decision_r") for tr in ents if tr.get("decision_r") is not None]
        return {
            "filled_entries": len(ents),
            "completed_exits": len(exs),
            "stop_loss": len(sls),
            "take_profit": len(tps),
            "position_closeout": len(posc),
            "trade_close": len(trc),
            "rejections": Counter(r["reason"] for r in rejs),
            **pl_stats(exs),
            "median_hold": pctile(holds, 0.5) if holds else None,
            "median_fill_r": pctile(fill_rs, 0.5) if fill_rs else None,
            "median_decision_r": pctile(dec_rs, 0.5) if dec_rs else None,
            "closeout": group_report(posc),
        }

    # rapid exits
    rapid = Counter()
    rapid_by = defaultdict(Counter)
    for tr in completed:
        for lab in rapid_bucket(tr.get("hold_sec")):
            rapid[lab] += 1
            rapid_by[tr.get("oanda_reason") or "?"][lab] += 1
            rapid_by[tr.get("build") or "?"][lab] += 1

    # re-entry
    seq = sorted(opened, key=lambda r: (r.get("symbol") or "", r.get("entry_time") or ""))
    reentry = Counter()
    reentry_build = defaultdict(Counter)
    last_close = {}  # (sym, side) -> (exit_ts, reason)
    last_any = {}
    completed_by_id = {tr["trade_id"]: tr for tr in completed}
    for tr in sorted(completed + opened, key=lambda r: r.get("entry_time") or r.get("exit_time") or ""):
        pass
    # walk completed in time, then look at next entry same symbol
    by_sym = defaultdict(list)
    for tr in opened:
        by_sym[tr.get("symbol")].append(tr)
    for sym, rows in by_sym.items():
        rows = sorted(rows, key=lambda r: r.get("entry_time") or "")
        for a, b in zip(rows, rows[1:]):
            if not a.get("exit_time") or not b.get("entry_time"):
                continue
            ta = parse_ts(a["exit_time"])
            tb = parse_ts(b["entry_time"])
            if not ta or not tb:
                continue
            dt = (tb - ta).total_seconds()
            if dt < 0:
                continue
            key = "any_close_to_next"
            def bump(cat, sec):
                for lim, name in ((60, "1m"), (120, "2m"), (300, "5m"), (600, "10m"), (1800, "30m")):
                    if sec <= lim:
                        reentry[f"{cat}<={name}"] += 1
                        reentry_build[a.get("build") or "?"][f"{cat}<={name}"] += 1
            bump(key, dt)
            if a.get("side") == b.get("side"):
                bump("same_dir", dt)
            else:
                bump("opp_dir", dt)
            if a.get("oanda_reason") == "STOP_LOSS_ORDER":
                bump("after_sl", dt)
                if a.get("side") == b.get("side"):
                    bump("sl_same_dir", dt)
                else:
                    bump("sl_opp_dir", dt)
            if a.get("oanda_reason") == "TAKE_PROFIT_ORDER":
                bump("after_tp", dt)
            if a.get("oanda_reason") == "MARKET_ORDER_POSITION_CLOSEOUT":
                bump("after_posclose", dt)

    # SL/TP distances
    sl_rows = []
    for tr in opened:
        fill = tr.get("entry_price")
        sl = tr.get("submitted_sl")
        tp = tr.get("submitted_tp")
        side = tr.get("side")
        pip = pip_size(tr.get("symbol") or "")
        if fill is None or sl is None or tp is None or not side:
            continue
        sl_pips = abs(fill - sl) / pip
        tp_pips = abs(fill - tp) / pip
        spr = tr.get("spread")
        spr_pips = (spr / pip) if spr else None
        sl_rows.append(
            {
                "symbol": tr.get("symbol"),
                "side": side,
                "build": tr.get("entry_build"),
                "sl_pips": sl_pips,
                "tp_pips": tp_pips,
                "fill_r": tr.get("fill_r"),
                "decision_r": tr.get("decision_r"),
                "spread_pips": spr_pips,
                "sl_spread": (sl_pips / spr_pips) if spr_pips else None,
                "tp_spread": (tp_pips / spr_pips) if spr_pips else None,
                "spread_over_tp": (spr / abs(tp - fill)) if abs(tp - fill) > 0 else None,
                "tp_le_1spr": spr is not None and abs(tp - fill) <= spr + 1e-12,
                "tp_le_2spr": spr is not None and abs(tp - fill) <= 2 * spr + 1e-12,
                "tp_le_3spr": spr is not None and abs(tp - fill) <= 3 * spr + 1e-12,
                "exit_reason": tr.get("oanda_reason"),
            }
        )

    # AUD 0.38R
    aud = None
    for tr in opened:
        if tr.get("symbol") == "AUD_USD" and tr.get("entry_price") is not None and abs(tr["entry_price"] - 0.71176) < 1e-8:
            aud = tr
            break
    # also scan all txs for the batch
    aud_batch = None
    if aud:
        aud_batch = [t for t in all_txs if str(t.get("batchID")) == aud.get("entry_batch") or str(t.get("id")) in {aud.get("entry_tx"), aud.get("exit_tx"), aud.get("entry_order_id")}]
        aud_detail = []
        for t in sorted(aud_batch, key=lambda x: int(x.get("id") or 0)):
            keep = {k: t[k] for k in t if k not in ("accountID", "userID", "homeConversionFactors")}
            if "fullPrice" in keep:
                fp = keep["fullPrice"]
                keep["fullPrice"] = {
                    "closeoutBid": fp.get("closeoutBid"),
                    "closeoutAsk": fp.get("closeoutAsk"),
                    "bids0": (fp.get("bids") or [{}])[0].get("price") if fp.get("bids") else None,
                    "asks0": (fp.get("asks") or [{}])[0].get("price") if fp.get("asks") else None,
                    "time": fp.get("time"),
                }
            aud_detail.append(keep)
    else:
        aud_detail = []

    # client order attempts vs fills vs rejects
    client_ids = {str(t.get("id")) for t in client_orders}
    cancel_by_order = {}
    for t in window:
        if t.get("type") == "ORDER_CANCEL":
            cancel_by_order[str(t.get("orderID"))] = t
    filled_client = set()
    for t in entry_fills:
        filled_client.add(str(t.get("orderID")))
    rejected_client = []
    for t in client_orders:
        oid = str(t.get("id"))
        if oid in filled_client:
            continue
        c = cancel_by_order.get(oid)
        rejected_client.append(
            {
                "order_id": oid,
                "time": t.get("time"),
                "symbol": t.get("instrument"),
                "units": t.get("units"),
                "cancel_reason": (c or {}).get("reason"),
                "build": classify_build(parse_ts(t.get("time"))),
                "sl": fnum((t.get("stopLossOnFill") or {}).get("price")),
                "tp": fnum((t.get("takeProfitOnFill") or {}).get("price")),
            }
        )

    # closing fill breakdown
    close_reason_pl = defaultdict(list)
    for tr in completed:
        close_reason_pl[tr.get("oanda_reason") or "other"].append(tr.get("realized_pl") or 0.0)

    sl_group = [tr for tr in completed if tr.get("oanda_reason") == "STOP_LOSS_ORDER"]
    tp_group = [tr for tr in completed if tr.get("oanda_reason") == "TAKE_PROFIT_ORDER"]

    def breakdown(rows, key):
        out = {}
        groups = defaultdict(list)
        for r in rows:
            groups[r.get(key)].append(r)
        for g, rs in groups.items():
            st = pl_stats(rs)
            holds = [x.get("hold_sec") for x in rs if x.get("hold_sec") is not None]
            st["median_hold"] = pctile(holds, 0.5) if holds else None
            out[str(g)] = st
        return out

    # first/last
    times = [t.get("time") for t in window]
    ids = [int(t.get("id") or 0) for t in window]

    summary = {
        "window_start_utc": window[0]["time"] if window else None,
        "window_end_utc": window[-1]["time"] if window else None,
        "window_filter": {"start": WIN_START, "end": WIN_END},
        "new_mgmt_start_utc": NEW_MGMT_START.isoformat(),
        "broker_exit_start_utc": BROKER_EXIT_START.isoformat(),
        "total_rows": len(window),
        "types": dict(types),
        "type_reason": {f"{a}|{b}": v for (a, b), v in type_reason.most_common()},
        "client_order": len(client_orders),
        "market_order": types.get("MARKET_ORDER", 0),
        "order_fill": types.get("ORDER_FILL", 0),
        "entry_fills": len(entry_fills),
        "rejected_unfilled_client": len(rejected_client),
        "rejected_client_reasons": Counter(r.get("cancel_reason") or "NO_CANCEL" for r in rejected_client),
        "rejection_events": len(rejections),
        "rejection_reasons": Counter(r["reason"] for r in rejections),
        "rejection_had_fill": sum(1 for r in rejections if r["had_fill"]),
        "rejection_opened_trade": sum(1 for r in rejections if r["fill_opened_trade"]),
        "closing_fills": len(completed),
        "close_reasons": {k: {"n": len(v), "pl": sum(v)} for k, v in close_reason_pl.items()},
        "realized": pl_stats(completed),
        "half_spread_cost_sum": sum(hsc),
        "half_spread_cost_n": len(hsc),
        "pair_pl": dict(pair_pl),
        "pair_n": dict(pair_n),
        "old": by_build("OLD_FAULTY_BUILD"),
        "new": by_build("NEW_FIXED_BUILD"),
        "boundary_completed": pl_stats([tr for tr in completed if tr.get("build") == "BOUNDARY_AMBIGUOUS"]),
        "old_filled": sum(1 for tr in opened if tr.get("entry_build") == "OLD_FAULTY_BUILD"),
        "new_filled": sum(1 for tr in opened if tr.get("entry_build") == "NEW_FIXED_BUILD"),
        "boundary_filled": sum(1 for tr in opened if tr.get("build") == "BOUNDARY_AMBIGUOUS"),
        "known_old_bug_present_old": any(tr.get("trade_id") in KNOWN_OLD_BUG for tr in completed),
        "known_old_bug_after_fix": any(
            tr.get("trade_id") in KNOWN_OLD_BUG and tr.get("exit_build") == "NEW_FIXED_BUILD"
            for tr in completed
        ),
        "closeouts": group_report(closeouts),
        "closeouts_by_class": {k: group_report(v) for k, v in closeout_by_class.items()},
        "closeout_hold_buckets": dict(Counter(hold_bucket(tr.get("hold_sec")) for tr in closeouts)),
        "sl": {
            **pl_stats(sl_group),
            "median_pl": pctile([r["realized_pl"] for r in sl_group if r.get("realized_pl") is not None], 0.5),
            "median_hold": pctile([r.get("hold_sec") for r in sl_group if r.get("hold_sec") is not None], 0.5),
            "by_pair": breakdown(sl_group, "symbol"),
            "by_side": breakdown(sl_group, "side"),
            "by_build": breakdown(sl_group, "build"),
        },
        "tp": {
            **pl_stats(tp_group),
            "median_pl": pctile([r["realized_pl"] for r in tp_group if r.get("realized_pl") is not None], 0.5),
            "median_hold": pctile([r.get("hold_sec") for r in tp_group if r.get("hold_sec") is not None], 0.5),
            "by_pair": breakdown(tp_group, "symbol"),
            "by_side": breakdown(tp_group, "side"),
            "by_build": breakdown(tp_group, "build"),
        },
        "decision_r": r_buckets("decision_r"),
        "fill_r": r_buckets("fill_r"),
        "decision_r_by_build": {
            "OLD_FAULTY_BUILD": dist_stats([tr["decision_r"] for tr in opened if tr.get("entry_build") == "OLD_FAULTY_BUILD" and tr.get("decision_r") is not None]),
            "NEW_FIXED_BUILD": dist_stats([tr["decision_r"] for tr in opened if tr.get("entry_build") == "NEW_FIXED_BUILD" and tr.get("decision_r") is not None]),
        },
        "fill_r_by_build": {
            "OLD_FAULTY_BUILD": dist_stats([tr["fill_r"] for tr in opened if tr.get("entry_build") == "OLD_FAULTY_BUILD" and tr.get("fill_r") is not None]),
            "NEW_FIXED_BUILD": dist_stats([tr["fill_r"] for tr in opened if tr.get("entry_build") == "NEW_FIXED_BUILD" and tr.get("fill_r") is not None]),
        },
        "fill_r_by_pair": {
            sym: dist_stats([tr["fill_r"] for tr in opened if tr.get("symbol") == sym and tr.get("fill_r") is not None])
            for sym in sorted({tr.get("symbol") for tr in opened})
        },
        "fill_r_by_side": {
            side: dist_stats([tr["fill_r"] for tr in opened if tr.get("side") == side and tr.get("fill_r") is not None])
            for side in ("BUY", "SELL")
        },
        "pair_direction": pair_dir_out,
        "rapid": dict(rapid),
        "rapid_by": {k: dict(v) for k, v in rapid_by.items()},
        "reentry": dict(reentry),
        "reentry_build": {k: dict(v) for k, v in reentry_build.items()},
        "sl_tp_dist": {
            "sl_pips": dist_stats([r["sl_pips"] for r in sl_rows]),
            "tp_pips": dist_stats([r["tp_pips"] for r in sl_rows]),
            "spread_pips": dist_stats([r["spread_pips"] for r in sl_rows if r.get("spread_pips") is not None]),
            "spread_over_tp": dist_stats([r["spread_over_tp"] for r in sl_rows if r.get("spread_over_tp") is not None]),
            "tp_le_1spr": sum(1 for r in sl_rows if r.get("tp_le_1spr")),
            "tp_le_2spr": sum(1 for r in sl_rows if r.get("tp_le_2spr")),
            "tp_le_3spr": sum(1 for r in sl_rows if r.get("tp_le_3spr")),
            "spread_over_tp_gt": {
                t: sum(1 for r in sl_rows if r.get("spread_over_tp") is not None and r["spread_over_tp"] > t)
                for t in (0.10, 0.15, 0.20, 0.25, 0.33, 0.50, 0.75, 1.00)
            },
        },
        "aud_038": aud,
        "aud_038_txs": aud_detail,
        "rejections": rejections,
        "rejected_unfilled": rejected_client,
        "completed_trades": [
            {
                k: tr.get(k)
                for k in (
                    "trade_id",
                    "symbol",
                    "side",
                    "units",
                    "entry_tx",
                    "entry_time",
                    "entry_price",
                    "exit_tx",
                    "exit_time",
                    "exit_price",
                    "realized_pl",
                    "oanda_reason",
                    "class",
                    "class_provisional",
                    "build",
                    "entry_build",
                    "exit_build",
                    "hold_sec",
                    "submitted_sl",
                    "submitted_tp",
                    "fill_r",
                    "decision_r",
                    "spread",
                    "inferred_mid",
                    "known_old_bug",
                    "client_order_id",
                )
            }
            for tr in sorted(completed, key=lambda r: r.get("entry_time") or "")
        ],
        "id_min": min(ids) if ids else None,
        "id_max": max(ids) if ids else None,
        "first_client_order": {
            "id": client_orders[0].get("id"),
            "time": client_orders[0].get("time"),
            "instrument": client_orders[0].get("instrument"),
        }
        if client_orders
        else None,
        "last_client_order": {
            "id": client_orders[-1].get("id"),
            "time": client_orders[-1].get("time"),
            "instrument": client_orders[-1].get("instrument"),
        }
        if client_orders
        else None,
    }
    OUT.write_text(json.dumps(summary, default=str), encoding="utf-8")
    print(
        "wrote",
        OUT.name,
        "rows",
        summary["total_rows"],
        "client",
        summary["client_order"],
        "fills",
        summary["entry_fills"],
        "closes",
        summary["closing_fills"],
        "pl",
        summary["realized"]["total_pl"],
    )


if __name__ == "__main__":
    main()

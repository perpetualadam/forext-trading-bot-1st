"""Read-only live-trade failure diagnosis. No orders, no production writes."""
from __future__ import annotations

import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import oandapyV20.endpoints.instruments as instruments

from forex_bot.oanda_client import _oanda_request, _to_oanda_rfc3339, get_api, oanda_instrument
from forex_bot.profit_protection import pip_size

BOUNDARY = datetime(2026, 9, 21, 22, 0, 4, tzinfo=timezone.utc)
HEADROOM = datetime(2026, 9, 22, 22, 28, 31, tzinfo=timezone.utc)
TELEGRAM = datetime(2026, 9, 24, 0, 44, 7, tzinfo=timezone.utc)
HORIZONS = (5, 15, 30, 60, 120, 240)
SYMBOLS = ("EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF")
DUMP = Path("/tmp/live_trade_dump.json")
OUT = Path("/tmp/live_trade_failure_analysis.json")


def _parse_ts(raw) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        dt = raw
    elif isinstance(raw, (int, float)) or (
        isinstance(raw, str) and raw.replace(".", "", 1).isdigit()
    ):
        try:
            dt = datetime.fromtimestamp(float(raw), tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    else:
        text = str(raw).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _f(v) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x):
        return None
    return x


def usd_dir(symbol: str, side: str) -> str:
    side = (side or "").upper()
    if symbol.startswith("USD_"):
        return "LONG_USD" if side == "BUY" else "SHORT_USD"
    if symbol.endswith("_USD"):
        return "SHORT_USD" if side == "BUY" else "LONG_USD"
    return "UNKNOWN"


def classify_exit(diag: dict) -> str:
    reason = str(diag.get("exit_reason") or "").lower()
    oanda = str(diag.get("oanda_reason") or "")
    otype = str(diag.get("oanda_transaction_type") or "")
    if reason == "broker_stop_loss" or oanda == "STOP_LOSS_ORDER":
        return "BROKER_STOP_LOSS"
    if reason == "broker_take_profit" or oanda == "TAKE_PROFIT_ORDER":
        return "BROKER_TAKE_PROFIT"
    if reason == "profit_protection":
        return "BOT_PROFIT_PROTECTION"
    if reason == "broker_manual_close" or oanda == "MARKET_ORDER_TRADE_CLOSE":
        return "MANUAL"
    if reason in ("weekend_flatten",):
        return "BOT_OTHER"
    if reason in ("sl_tp",):
        return "BOT_OTHER"
    if not reason:
        return "UNKNOWN"
    return "UNKNOWN"


def mfe_bucket(mfe_r: float | None) -> str:
    if mfe_r is None:
        return "UNKNOWN"
    if mfe_r < 0.25:
        return "A:<0.25R"
    if mfe_r < 0.5:
        return "B:0.25-0.5R"
    if mfe_r < 1.0:
        return "C:0.5-1.0R"
    if mfe_r < 1.5:
        return "D:1.0-1.5R"
    if mfe_r < 2.0:
        return "E:1.5-2.0R"
    return "F:>=2.0R"


def fetch_ba_m5(symbol: str, start: datetime, end: datetime) -> list[dict]:
    api = get_api()
    if api is None:
        return []
    rows: list[dict] = []
    cur = start
    while cur < end:
        chunk_to = min(cur + timedelta(hours=36), end)
        params = {
            "granularity": "M5",
            "from": _to_oanda_rfc3339(cur.replace(tzinfo=None)),
            "to": _to_oanda_rfc3339(chunk_to.replace(tzinfo=None)),
            "price": "BA",
        }
        req = instruments.InstrumentsCandles(instrument=oanda_instrument(symbol), params=params)
        data = _oanda_request(api, req, context=f"BA {symbol}")
        candles = data.get("candles") or []
        if not candles:
            cur = chunk_to
            continue
        last = None
        for c in candles:
            if not c.get("complete", True):
                continue
            bid = c.get("bid") or {}
            ask = c.get("ask") or {}
            if not bid or not ask:
                continue
            ts = _parse_ts(c.get("time"))
            if ts is None:
                continue
            rows.append(
                {
                    "ts": ts.isoformat(),
                    "bid_o": float(bid["o"]),
                    "bid_h": float(bid["h"]),
                    "bid_l": float(bid["l"]),
                    "bid_c": float(bid["c"]),
                    "ask_o": float(ask["o"]),
                    "ask_h": float(ask["h"]),
                    "ask_l": float(ask["l"]),
                    "ask_c": float(ask["c"]),
                }
            )
            last = ts
        cur = (last + timedelta(minutes=5)) if last else chunk_to
    return rows


def bars_between(bars: list[dict], start: datetime, end: datetime) -> list[dict]:
    out = []
    for b in bars:
        ts = _parse_ts(b["ts"])
        if ts is None:
            continue
        if start < ts <= end:
            out.append(b)
    return out


def path_mfe_mae(side: str, entry: float, pip: float, bars: list[dict]) -> tuple[float, float]:
    """Executable-side MFE/MAE in pips from M5 bid/ask extremes. Intra-bar order unknown."""
    mfe = 0.0
    mae = 0.0
    side = side.upper()
    for b in bars:
        if side == "BUY":
            fav = (b["bid_h"] - entry) / pip
            adv = (entry - b["bid_l"]) / pip
        else:
            fav = (entry - b["ask_l"]) / pip
            adv = (b["ask_h"] - entry) / pip
        if fav > mfe:
            mfe = fav
        if adv > mae:
            mae = adv
    return mfe, mae


def close_at(side: str, bars: list[dict], entry_ts: datetime, minutes: int) -> float | None:
    target = entry_ts + timedelta(minutes=minutes)
    chosen = None
    for b in bars:
        ts = _parse_ts(b["ts"])
        if ts is None or ts <= entry_ts:
            continue
        if ts > target:
            break
        chosen = b
    if chosen is None:
        return None
    return chosen["bid_c"] if side.upper() == "BUY" else chosen["ask_c"]


def first_touch(side: str, entry: float, sl: float, tp: float, bars: list[dict]) -> str:
    side = side.upper()
    for b in bars:
        if side == "BUY":
            hit_sl = b["bid_l"] <= sl
            hit_tp = b["bid_h"] >= tp
        else:
            hit_sl = b["ask_h"] >= sl
            hit_tp = b["ask_l"] <= tp
        if hit_sl and hit_tp:
            return "AMBIGUOUS"
        if hit_sl:
            return "SL"
        if hit_tp:
            return "TP"
    return "OPEN"


def pre_move(side: str, bars_before: list[dict], minutes: int, pip: float) -> float | None:
    if not bars_before:
        return None
    end = bars_before[-1]
    cutoff = _parse_ts(end["ts"])
    if cutoff is None:
        return None
    start_ts = cutoff - timedelta(minutes=minutes)
    start = None
    for b in bars_before:
        ts = _parse_ts(b["ts"])
        if ts is not None and ts >= start_ts:
            start = b
            break
    if start is None:
        return None
    if side.upper() == "BUY":
        return (end["bid_c"] - start["bid_c"]) / pip
    return (start["ask_c"] - end["ask_c"]) / pip


def swing_ext(side: str, bars_before: list[dict], pip: float) -> dict:
    look = bars_before[-36:] if len(bars_before) > 36 else bars_before
    if not look:
        return {"swing_pips": None, "extended": None}
    last = look[-1]
    if side.upper() == "BUY":
        swing = max(b["bid_h"] for b in look)
        dist = (swing - last["bid_c"]) / pip
    else:
        swing = min(b["ask_l"] for b in look)
        dist = (last["ask_c"] - swing) / pip
    return {"swing_pips": round(dist, 3), "extended": bool(dist <= 2.0)}


def mean(xs: list[float]) -> float | None:
    if not xs:
        return None
    return sum(xs) / len(xs)


def summarize(rows: list[dict], key: str) -> dict:
    vals = [_f(r.get(key)) for r in rows]
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"n": 0}
    return {
        "n": len(vals),
        "mean": round(mean(vals), 4),
        "median": round(sorted(vals)[len(vals) // 2], 4),
        "sum": round(sum(vals), 4),
    }


def group_stats(rows: list[dict], field: str) -> dict:
    groups = defaultdict(list)
    for r in rows:
        groups[str(r.get(field) or "unknown")].append(r)
    out = {}
    for name, items in sorted(groups.items()):
        sl = [i for i in items if i["exit_class"] == "BROKER_STOP_LOSS"]
        tp = [i for i in items if i["exit_class"] == "BROKER_TAKE_PROFIT"]
        pp = [i for i in items if i["exit_class"] == "BOT_PROFIT_PROTECTION"]
        scored = [i for i in items if i["exit_class"] in ("BROKER_STOP_LOSS", "BROKER_TAKE_PROFIT", "BOT_PROFIT_PROTECTION")]
        rs = [_f(i.get("realised_r")) for i in scored]
        rs = [x for x in rs if x is not None]
        wins = [x for x in rs if x > 0]
        losses = [x for x in rs if x < 0]
        gp = sum(wins)
        gl = abs(sum(losses))
        out[name] = {
            "n": len(items),
            "sl": len(sl),
            "tp": len(tp),
            "pp": len(pp),
            "sl_pct": round(100 * len(sl) / len(items), 1) if items else 0,
            "mean_r": round(mean(rs), 4) if rs else None,
            "sum_r": round(sum(rs), 4) if rs else None,
            "win_rate": round(len(wins) / len(rs), 3) if rs else None,
            "profit_factor": round(gp / gl, 3) if gl else (float("inf") if gp else None),
        }
    return out


def main() -> None:
    dump = json.loads(DUMP.read_text(encoding="utf-8"))
    orders = dump["exec_orders"]
    by_broker = {str(o.get("broker_order_id")): o for o in orders if o.get("broker_order_id")}
    candles: dict[str, list[dict]] = {}
    start = BOUNDARY - timedelta(hours=6)
    end = min(datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc), datetime.now(timezone.utc) - timedelta(minutes=10))
    print("fetching M5 BA", flush=True)
    for sym in SYMBOLS:
        candles[sym] = fetch_ba_m5(sym, start, end)
        print(sym, len(candles[sym]), flush=True)

    trades = []
    for t in dump["trades"]:
        if t.get("execution_kind") != "live" or t.get("trading_mode") != "live":
            continue
        exit_ts = _parse_ts(t.get("time"))
        if exit_ts is None or exit_ts < BOUNDARY:
            continue
        diag = t.get("diagnostics") or {}
        if not isinstance(diag, dict):
            continue
        side = str(t.get("direction") or diag.get("direction") or "").upper()
        symbol = str(t.get("symbol") or diag.get("symbol") or "")
        entry_ts = _parse_ts(diag.get("entry_time"))
        if entry_ts is None or entry_ts == exit_ts:
            bid0 = str(diag.get("broker_trade_id") or "")
            order0 = by_broker.get(bid0) if bid0 else None
            if order0:
                entry_ts = _parse_ts(order0.get("filled_at") or order0.get("created_at"))
            else:
                cands = []
                for o2 in orders:
                    if o2.get("symbol") != symbol:
                        continue
                    if str(o2.get("side") or "").upper() != side:
                        continue
                    ft = _parse_ts(o2.get("filled_at") or o2.get("created_at"))
                    if ft and exit_ts and ft <= exit_ts:
                        cands.append((exit_ts - ft, ft))
                cands.sort()
                if cands and cands[0][0] <= timedelta(hours=6):
                    entry_ts = cands[0][1]
        if entry_ts is None:
            entry_ts = exit_ts
        entry = _f(diag.get("entry_price") or t.get("entry_price"))
        exit_px = _f(diag.get("exit_price") or t.get("exit_price"))
        sl = _f(diag.get("original_sl"))
        tp = _f(diag.get("original_tp"))
        sl_pips = _f(diag.get("original_sl_pips"))
        tp_pips = _f(diag.get("original_tp_pips"))
        pip = pip_size(symbol)
        if sl_pips is None and entry is not None and sl is not None:
            sl_pips = abs(entry - sl) / pip
        if tp_pips is None and entry is not None and tp is not None:
            tp_pips = abs(tp - entry) / pip
        r_ratio = (tp_pips / sl_pips) if sl_pips and tp_pips else None
        bid = str(diag.get("broker_trade_id") or "")
        order = by_broker.get(bid) or {}
        meta = order.get("metadata") if isinstance(order.get("metadata"), dict) else {}
        exec_ref = _f(meta.get("executable_reference"))
        mid = _f(meta.get("mid"))
        spread_pips = None
        if exec_ref is not None and mid is not None:
            spread_pips = abs(exec_ref - mid) * 2.0 / pip
        atr = _f(diag.get("atr_at_entry_pips"))
        mfe = _f(diag.get("mfe_pips"))
        mae = _f(diag.get("mae_pips"))
        mfe_r = _f(diag.get("mfe_r"))
        if mfe_r is None and mfe is not None and sl_pips:
            mfe_r = mfe / sl_pips
        mae_r = (mae / sl_pips) if mae is not None and sl_pips else None
        realised_r = _f(diag.get("realised_r"))
        hold = (exit_ts - entry_ts).total_seconds() if entry_ts and exit_ts else None
        bars = candles.get(symbol) or []
        path = bars_between(bars, entry_ts, exit_ts) if entry_ts and exit_ts else []
        recon_mfe = recon_mae = None
        if entry is not None and path:
            recon_mfe, recon_mae = path_mfe_mae(side, entry, pip, path)
        before = [b for b in bars if (_parse_ts(b["ts"]) or exit_ts) <= entry_ts]
        fwd = {}
        dir_ok = {}
        for h in HORIZONS:
            px = close_at(side, bars, entry_ts, h)
            if px is None or entry is None:
                fwd[str(h)] = None
                dir_ok[str(h)] = None
                continue
            pips = (px - entry) / pip if side == "BUY" else (entry - px) / pip
            r = pips / sl_pips if sl_pips else None
            fwd[str(h)] = {"pips": round(pips, 3), "r": None if r is None else round(r, 4)}
            dir_ok[str(h)] = bool(pips > 0)
        pre = {str(m): pre_move(side, before, m, pip) for m in (5, 15, 30)}
        swing = swing_ext(side, before, pip)
        hour_utc = entry_ts.hour
        rec = {
            "id": t.get("id"),
            "symbol": symbol,
            "side": side,
            "strategy": t.get("strategy"),
            "entry_ts": entry_ts.isoformat(),
            "exit_ts": exit_ts.isoformat(),
            "entry_price": entry,
            "exit_price": exit_px,
            "sl": sl,
            "tp": tp,
            "sl_pips": sl_pips,
            "tp_pips": tp_pips,
            "initial_r": None if r_ratio is None else round(r_ratio, 3),
            "exit_class": classify_exit(diag),
            "hold_sec": hold,
            "mfe_pips": mfe,
            "mae_pips": mae,
            "mfe_r": None if mfe_r is None else round(mfe_r, 4),
            "mae_r": None if mae_r is None else round(mae_r, 4),
            "recon_mfe_pips": None if recon_mfe is None else round(recon_mfe, 3),
            "recon_mae_pips": None if recon_mae is None else round(recon_mae, 3),
            "realised_pips": _f(diag.get("realised_pips")),
            "realised_r": realised_r,
            "pnl": _f(t.get("pnl")),
            "atr_pips": atr,
            "stop_over_atr": (sl_pips / atr) if sl_pips and atr else None,
            "spread_pips": None if spread_pips is None else round(spread_pips, 3),
            "stop_over_spread": (sl_pips / spread_pips) if sl_pips and spread_pips else None,
            "usd_dir": usd_dir(symbol, side),
            "hour_utc": hour_utc,
            "mfe_bucket": mfe_bucket(mfe_r),
            "pp_activated": bool(diag.get("profit_protection_activated")),
            "giveback_pips": _f(diag.get("mfe_giveback_pips")),
            "giveback_r": (
                None
                if sl_pips in (None, 0) or _f(diag.get("mfe_giveback_pips")) is None
                else round(_f(diag.get("mfe_giveback_pips")) / sl_pips, 4)
            ),
            "forward": fwd,
            "dir_correct": dir_ok,
            "pre_move_pips": {k: None if v is None else round(v, 3) for k, v in pre.items()},
            "swing": swing,
            "oanda_reason": diag.get("oanda_reason"),
            "broker_trade_id": bid or None,
            "in_headroom": exit_ts >= HEADROOM,
            "in_telegram": exit_ts >= TELEGRAM,
        }
        trades.append(rec)

    scored = [
        r
        for r in trades
        if r["exit_class"] in ("BROKER_STOP_LOSS", "BROKER_TAKE_PROFIT", "BOT_PROFIT_PROTECTION")
    ]
    stopped = [r for r in trades if r["exit_class"] == "BROKER_STOP_LOSS"]
    buckets = Counter(r["mfe_bucket"] for r in stopped)

    # counterfactual target R using reconstructed first-touch until +240m
    target_cf = {}
    for label, mult in (("1.0R", 1.0), ("1.5R", 1.5), ("2.0R", 2.0)):
        hits = []
        for r in scored:
            if r["entry_price"] is None or not r["sl_pips"] or not r["sl"] or not r["tp"]:
                continue
            entry = r["entry_price"]
            sl = r["sl"]
            sl_pips = r["sl_pips"]
            side = r["side"]
            pip = pip_size(r["symbol"])
            tp = entry + (mult * sl_pips * pip if side == "BUY" else -mult * sl_pips * pip)
            bars = candles.get(r["symbol"]) or []
            path = bars_between(bars, _parse_ts(r["entry_ts"]), _parse_ts(r["entry_ts"]) + timedelta(hours=8))
            hit = first_touch(side, entry, sl, tp, path)
            if hit == "TP":
                hits.append(mult)
            elif hit == "SL":
                hits.append(-1.0)
            elif hit == "AMBIGUOUS":
                continue
            else:
                continue
        wins = [x for x in hits if x > 0]
        losses = [x for x in hits if x < 0]
        gl = abs(sum(losses))
        target_cf[label] = {
            "resolved": len(hits),
            "tp": len(wins),
            "sl": len(losses),
            "win_rate": round(len(wins) / len(hits), 3) if hits else None,
            "mean_r": round(mean(hits), 4) if hits else None,
            "sum_r": round(sum(hits), 4) if hits else None,
            "profit_factor": round(sum(wins) / gl, 3) if gl else None,
        }

    sl_cf = {}
    for label, atr_mult in (("2.0ATR", 2.0), ("2.5ATR", 2.5), ("3.0ATR", 3.0)):
        hits = []
        for r in scored:
            if r["entry_price"] is None or not r["atr_pips"] or not r["sl_pips"]:
                continue
            entry = r["entry_price"]
            atr = r["atr_pips"]
            sl_pips_new = atr_mult * atr
            pip = pip_size(r["symbol"])
            side = r["side"]
            sl = entry - sl_pips_new * pip if side == "BUY" else entry + sl_pips_new * pip
            tp_pips = r["tp_pips"] or (2.0 * r["sl_pips"])
            tp = entry + (tp_pips * pip if side == "BUY" else -tp_pips * pip)
            bars = candles.get(r["symbol"]) or []
            path = bars_between(bars, _parse_ts(r["entry_ts"]), _parse_ts(r["entry_ts"]) + timedelta(hours=8))
            hit = first_touch(side, entry, sl, tp, path)
            # constant-risk R = pips / new_stop
            if hit == "TP":
                hits.append(tp_pips / sl_pips_new)
            elif hit == "SL":
                hits.append(-1.0)
            elif hit == "AMBIGUOUS":
                continue
        wins = [x for x in hits if x > 0]
        losses = [x for x in hits if x < 0]
        gl = abs(sum(losses))
        sl_cf[label] = {
            "resolved": len(hits),
            "tp": len(wins),
            "sl": len(losses),
            "win_rate": round(len(wins) / len(hits), 3) if hits else None,
            "mean_r": round(mean(hits), 4) if hits else None,
            "sum_r": round(sum(hits), 4) if hits else None,
            "profit_factor": round(sum(wins) / gl, 3) if gl else None,
        }

    # USD overlap clusters: SL exits whose hold overlapped another SL in same USD dir
    clusters = []
    sl_sorted = sorted(stopped, key=lambda r: r["entry_ts"] or "")
    used = set()
    for i, a in enumerate(sl_sorted):
        if a["id"] in used:
            continue
        group = [a]
        a0, a1 = _parse_ts(a["entry_ts"]), _parse_ts(a["exit_ts"])
        for b in sl_sorted[i + 1 :]:
            if a["usd_dir"] != b["usd_dir"]:
                continue
            b0, b1 = _parse_ts(b["entry_ts"]), _parse_ts(b["exit_ts"])
            if a0 and a1 and b0 and b1 and a0 < b1 and b0 < a1:
                group.append(b)
                used.add(b["id"])
        if len(group) >= 2:
            used.add(a["id"])
            clusters.append(
                {
                    "usd_dir": a["usd_dir"],
                    "n": len(group),
                    "symbols": [g["symbol"] for g in group],
                    "ids": [g["id"] for g in group],
                    "entry": a["entry_ts"],
                }
            )

    fwd_sum = {}
    for h in HORIZONS:
        for subset_name, subset in (
            ("all_scored", scored),
            ("BUY", [r for r in scored if r["side"] == "BUY"]),
            ("SELL", [r for r in scored if r["side"] == "SELL"]),
            ("stopped", stopped),
        ):
            rs = []
            ok = []
            for r in subset:
                cell = (r.get("forward") or {}).get(str(h))
                if cell and cell.get("r") is not None:
                    rs.append(cell["r"])
                flag = (r.get("dir_correct") or {}).get(str(h))
                if flag is not None:
                    ok.append(1 if flag else 0)
            fwd_sum.setdefault(str(h), {})[subset_name] = {
                "n": len(rs),
                "mean_r": None if not rs else round(mean(rs), 4),
                "dir_hit": None if not ok else round(sum(ok) / len(ok), 3),
            }

    pp = [r for r in trades if r["exit_class"] == "BOT_PROFIT_PROTECTION"]
    report = {
        "boundary_utc": BOUNDARY.isoformat(),
        "headroom_utc": HEADROOM.isoformat(),
        "telegram_utc": TELEGRAM.isoformat(),
        "n_trades": len(trades),
        "exit_breakdown": dict(Counter(r["exit_class"] for r in trades)),
        "scored_n": len(scored),
        "by_symbol": group_stats(scored, "symbol"),
        "by_side": group_stats(scored, "side"),
        "by_strategy": group_stats(scored, "strategy"),
        "by_usd": group_stats(scored, "usd_dir"),
        "by_hour": group_stats(scored, "hour_utc"),
        "stopped_n": len(stopped),
        "stopped_buckets": dict(buckets),
        "stopped_bucket_pct": {
            k: round(100 * v / len(stopped), 1) for k, v in buckets.items()
        }
        if stopped
        else {},
        "mfe": summarize(scored, "mfe_r"),
        "mae": summarize(scored, "mae_r"),
        "stopped_mfe": summarize(stopped, "mfe_r"),
        "stopped_mae": summarize(stopped, "mae_r"),
        "mean_stop_over_atr": summarize(scored, "stop_over_atr"),
        "mean_spread": summarize(scored, "spread_pips"),
        "mean_stop_over_spread": summarize(scored, "stop_over_spread"),
        "pre_move": {
            m: summarize(
                [
                    {"v": (r.get("pre_move_pips") or {}).get(m)}
                    for r in stopped
                    if (r.get("pre_move_pips") or {}).get(m) is not None
                ],
                "v",
            )
            for m in ("5", "15", "30")
        },
        "stopped_extended": sum(1 for r in stopped if (r.get("swing") or {}).get("extended")),
        "forward": fwd_sum,
        "target_cf": target_cf,
        "sl_width_cf": sl_cf,
        "usd_clusters": {"n_clusters": len(clusters), "trades_in_clusters": sum(c["n"] for c in clusters), "examples": clusters[:12]},
        "pp": {
            "n": len(pp),
            "mean_mfe_r": summarize(pp, "mfe_r"),
            "mean_exit_r": summarize(pp, "realised_r"),
            "mean_giveback_r": summarize(pp, "giveback_r"),
            "mean_hold_sec": summarize(pp, "hold_sec"),
            "would_reach_2r_mfe": sum(1 for r in pp if (r.get("mfe_r") or 0) >= 2.0),
        },
        "headroom_subset": dict(Counter(r["exit_class"] for r in trades if r["in_headroom"])),
        "telegram_subset": dict(Counter(r["exit_class"] for r in trades if r["in_telegram"])),
        "candle_counts": {k: len(v) for k, v in candles.items()},
        "trades": trades,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("wrote", OUT, "n", len(trades), "exits", report["exit_breakdown"])


if __name__ == "__main__":
    os.environ.setdefault("OANDA_CHUNK_DELAY_SEC", "0.15")
    main()

"""READ-ONLY reconstruction for STOP_LOSS_ON_FILL_LOSS forensic.

GET InstrumentsCandles only. Never writes to OANDA or the database.
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent / "_sl_on_fill_analysis.json"

PIPS = {
    "GBP_USD": 0.0001,
    "AUD_USD": 0.0001,
    "USD_CHF": 0.0001,
    "USD_CAD": 0.0001,
    "USD_JPY": 0.01,
    "EUR_USD": 0.0001,
}

CANCELS = [
    ("cid-34ea03ffe3fa486ab98e7bad36d45252", "GBP_USD", "BUY", 1, "swing_trend", 1.3347),
    ("cid-8f55b3f86c5d4f2b918f5ee1d56baef0", "USD_JPY", "SELL", 2, "swing_trend", 157.37),
    ("cid-6d0d82b0369e4f10b370dca4802b0af2", "GBP_USD", "BUY", 1, "swing_trend", 1.3347),
    ("cid-03209f355b264a10b11548a57443d6a7", "AUD_USD", "BUY", 3, "swing_mean_reversion", 0.71173),
    ("cid-3ac32014576e44ea986041bc7c85b447", "USD_JPY", "SELL", 2, "scalp", 157.37),
    ("cid-cb964084bab6490b87f5606bebbaee98", "AUD_USD", "BUY", 3, "swing_mean_reversion", 0.71173),
    ("cid-eee7fdf92db44f61864421b14ff0ab19", "USD_CHF", "SELL", 2, "swing_trend", 0.82065),
    ("cid-84c40a5c859e4bed8c20118ef9cf5cd7", "USD_CHF", "SELL", 2, "swing_mean_reversion", 0.82065),
    ("cid-74595fd264cd484db786041a46582036", "GBP_USD", "BUY", 1, "swing_mean_reversion", 1.33448),
    ("cid-ac380f6a32914d59a20e8a2dbc9ee488", "USD_CAD", "SELL", 2, "swing_mean_reversion", 1.4063),
    ("cid-683e7c2d6f0a404ea4387efb01892d6d", "USD_CAD", "SELL", 2, "swing_trend", 1.4063),
    ("cid-e6afc545a3d844529fc229dec57cceec", "GBP_USD", "BUY", 1, "swing_trend", 1.33462),
    ("cid-bdb651433a0a4403b6802c46a466d733", "GBP_USD", "BUY", 1, "swing_trend", 1.33462),
    ("cid-b2db42bf9263435983665c6b4df3b4ea", "GBP_USD", "BUY", 1, "swing_breakout", 1.33462),
    ("cid-8bde28710212487b9d9df455a32fe8a8", "GBP_USD", "BUY", 1, "swing_trend", 1.33462),
    ("cid-57588c279fc2440d8f4c24abd12c09e2", "GBP_USD", "BUY", 1, "swing_mean_reversion", 1.33427),
    ("cid-4fc845893cd149e4b6d7590920e95fac", "GBP_USD", "BUY", 1, "swing_mean_reversion", 1.33427),
    ("cid-ba84f573b35b4a16a5b91ff3012bb632", "AUD_USD", "BUY", 3, "swing_trend", 0.71148),
    ("cid-3c886c582acb4550b413eb2f08c125bb", "AUD_USD", "BUY", 3, "swing_breakout", 0.71166),
]


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, val = raw.split("=", 1)
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = val


def pct(xs: list[float], p: float) -> float:
    if not xs:
        return float("nan")
    ys = sorted(xs)
    if len(ys) == 1:
        return ys[0]
    k = (len(ys) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return ys[int(k)]
    return ys[f] + (ys[c] - ys[f]) * (k - f)


def stats(xs: list[float]) -> dict:
    xs = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    if not xs:
        return {"n": 0}
    return {
        "n": len(xs),
        "min": min(xs),
        "p25": pct(xs, 0.25),
        "median": median(xs),
        "p75": pct(xs, 0.75),
        "max": max(xs),
    }


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def main() -> None:
    _load_dotenv()
    from oandapyV20.endpoints.instruments import InstrumentsCandles

    from forex_bot.config import Config
    from forex_bot.oanda_client import _oanda_request, get_api

    tx_path = Path(__file__).resolve().parent / "_missing_fill_oanda_tx.json"
    raw = json.loads(tx_path.read_text(encoding="utf-8"))
    txs = raw["transactions"]
    by_cid = {}
    by_id = {str(t.get("id")): t for t in txs}
    for t in txs:
        cid = (t.get("clientExtensions") or {}).get("id")
        if cid and t.get("type") == "MARKET_ORDER":
            by_cid[cid] = t

    api = get_api()
    aid = (Config.OANDA_ACCOUNT_ID or os.getenv("OANDA_ACCOUNT_ID") or "").strip()
    if api is None or not aid:
        raise SystemExit("OANDA API unavailable")

    start = "2026-09-22T20:45:00.000000000Z"
    end = "2026-09-22T21:50:00.000000000Z"
    candles: dict[str, list] = {}
    for inst in ("GBP_USD", "USD_JPY", "AUD_USD", "USD_CHF", "USD_CAD"):
        req = InstrumentsCandles(
            instrument=inst,
            params={
                "granularity": "M1",
                "price": "MBA",
                "from": start,
                "to": end,
            },
        )
        resp = _oanda_request(api, req, context=f"m1 {inst}")
        candles[inst] = resp.get("candles") or []

    m5: dict[str, list] = {}
    for inst in ("GBP_USD", "USD_JPY", "AUD_USD", "USD_CHF", "USD_CAD"):
        req = InstrumentsCandles(
            instrument=inst,
            params={
                "granularity": "M5",
                "price": "M",
                "from": "2026-09-22T18:00:00.000000000Z",
                "to": end,
            },
        )
        resp = _oanda_request(api, req, context=f"m5 {inst}")
        m5[inst] = resp.get("candles") or []

    def bar_at(inst: str, ts: datetime) -> dict | None:
        best = None
        for c in candles.get(inst) or []:
            ct = parse_ts(str(c.get("time")))
            if ct <= ts:
                best = c
            else:
                break
        return best

    def m1_range_after(inst: str, ts: datetime, minutes: int = 2) -> dict:
        end_t = ts + timedelta(minutes=minutes)
        highs_bid, lows_ask, spreads = [], [], []
        for c in candles.get(inst) or []:
            ct = parse_ts(str(c.get("time")))
            if ts - timedelta(seconds=30) <= ct <= end_t:
                bid, ask = c.get("bid") or {}, c.get("ask") or {}
                if bid.get("h") and ask.get("l"):
                    highs_bid.append(float(bid["h"]))
                    lows_ask.append(float(ask["l"]))
                if bid.get("c") and ask.get("c"):
                    spreads.append(float(ask["c"]) - float(bid["c"]))
        return {"highs_bid": highs_bid, "lows_ask": lows_ask, "spreads": spreads}

    def atr14(inst: str, ts: datetime) -> float | None:
        rows = []
        for c in m5.get(inst) or []:
            if not c.get("complete"):
                continue
            ct = parse_ts(str(c.get("time")))
            mid = c.get("mid") or {}
            if ct + timedelta(minutes=5) <= ts and mid.get("h"):
                rows.append((float(mid["h"]), float(mid["l"]), float(mid["c"])))
        if len(rows) < 15:
            return None
        rows = rows[-15:]
        trs = []
        prev_c = rows[0][2]
        for h, l, c in rows[1:]:
            trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
            prev_c = c
        return sum(trs) / len(trs) if trs else None

    cancelled = []
    for cid, inst, side, units, strat, mid in CANCELS:
        mo = by_cid[cid]
        sl = float(mo["stopLossOnFill"]["price"])
        tp = float(mo["takeProfitOnFill"]["price"])
        cancel = next(
            t
            for t in txs
            if t.get("type") == "ORDER_CANCEL" and str(t.get("orderID")) == str(mo["id"])
        )
        pip = PIPS[inst]
        if side == "BUY":
            sl_d = (tp - sl) / 3.0
            xref = sl + sl_d
            headroom = xref - sl
            orient = sl < xref < tp
        else:
            sl_d = (sl - tp) / 3.0
            xref = sl - sl_d
            headroom = sl - xref
            orient = tp < xref < sl
        t4 = parse_ts(mo["time"])
        bar = bar_at(inst, t4)
        bid_c = ask_c = spread = None
        if bar:
            bid_c = float((bar.get("bid") or {}).get("c")) if (bar.get("bid") or {}).get("c") else None
            ask_c = float((bar.get("ask") or {}).get("c")) if (bar.get("ask") or {}).get("c") else None
            if bid_c and ask_c:
                spread = ask_c - bid_c
        atr = atr14(inst, t4)
        # OANDA SL-on-fill vs trigger side at candle close
        # BUY long SL triggers on bid; invalid if bid <= SL
        # SELL short SL triggers on ask; invalid if ask >= SL
        sl_vs_trigger = None
        headroom_vs_trigger = None
        if side == "BUY" and bid_c is not None:
            sl_vs_trigger = bid_c - sl
            headroom_vs_trigger = bid_c - sl
        elif side == "SELL" and ask_c is not None:
            sl_vs_trigger = sl - ask_c
            headroom_vs_trigger = sl - ask_c
        cancelled.append(
            {
                "cid": cid,
                "instrument": inst,
                "side": side,
                "units": units,
                "strategy": strat,
                "mid": mid,
                "mo_id": mo["id"],
                "cancel_id": cancel["id"],
                "reason": cancel.get("reason"),
                "time": mo["time"],
                "sl": sl,
                "tp": tp,
                "implied_sl_d": sl_d,
                "implied_xref": xref,
                "implied_r": 2.0,
                "headroom": headroom,
                "headroom_pips": headroom / pip,
                "stop_pips": sl_d / pip,
                "orient_valid_vs_implied_xref": orient,
                "m1_bid_c": bid_c,
                "m1_ask_c": ask_c,
                "m1_spread": spread,
                "m1_spread_pips": None if spread is None else spread / pip,
                "stop_over_spread": None
                if spread in (None, 0)
                else sl_d / spread,
                "atr14_m5": atr,
                "atr_pips": None if atr is None else atr / pip,
                "sl_d_over_atr": None if not atr else sl_d / atr,
                "implied_2atr": None if atr is None else 2.0 * atr,
                "headroom_vs_m1_trigger": headroom_vs_trigger,
                "headroom_vs_m1_trigger_pips": None
                if headroom_vs_trigger is None
                else headroom_vs_trigger / pip,
                "m1_bar_time": None if not bar else bar.get("time"),
            }
        )

    # Successful controls in window
    success_cids = [
        "cid-f0018527cf024210bf211e9df62dd1ea",
        "cid-239ddf6d18aa4f8d8a4d179949dd5c5f",
        "cid-868759c88fbf4106b7a450820dcd636d",
        "cid-4ddd3a933d47430aa4af478ebeef0267",
        "cid-0ff3d11b90464e358a077106d229d8eb",
    ]
    # metadata from prior query
    succ_meta = {
        "cid-f0018527cf024210bf211e9df62dd1ea": {
            "symbol": "USD_JPY",
            "side": "SELL",
            "mid": 157.4,
            "xref": 157.374,
            "sl": 157.431,
            "tp": 157.261,
            "fill": 157.374,
            "created": "2026-09-22T20:52:51.350855+00:00",
        },
        "cid-239ddf6d18aa4f8d8a4d179949dd5c5f": {
            "symbol": "USD_JPY",
            "side": "BUY",
            "mid": 157.44,
            "xref": 157.463,
            "sl": 157.412,
            "tp": 157.564,
            "fill": 157.463,
            "created": "2026-09-22T21:21:22.05917+00:00",
        },
        "cid-868759c88fbf4106b7a450820dcd636d": {
            "symbol": "USD_JPY",
            "side": "BUY",
            "mid": 157.44,
            "xref": 157.444,
            "sl": 157.393,
            "tp": 157.545,
            "fill": 157.444,
            "created": "2026-09-22T21:23:24.542236+00:00",
        },
        "cid-4ddd3a933d47430aa4af478ebeef0267": {
            "symbol": "GBP_USD",
            "side": "BUY",
            "mid": 1.33447,
            "xref": 1.33461,
            "sl": 1.33413,
            "tp": 1.33557,
            "fill": 1.33461,
            "created": "2026-09-22T21:35:37.456237+00:00",
        },
        "cid-0ff3d11b90464e358a077106d229d8eb": {
            "symbol": "USD_JPY",
            "side": "BUY",
            "mid": 157.402,
            "xref": 157.421,
            "sl": 157.378,
            "tp": 157.508,
            "fill": 157.421,
            "created": "2026-09-22T21:41:44.563269+00:00",
        },
    }
    successful = []
    for cid in success_cids:
        mo = by_cid.get(cid)
        meta = succ_meta[cid]
        inst = meta["symbol"]
        pip = PIPS[inst]
        xref = meta["xref"]
        sl = meta["sl"]
        tp = meta["tp"]
        fill = meta["fill"]
        side = meta["side"]
        sl_d = (xref - sl) if side == "BUY" else (sl - xref)
        t_created = parse_ts(meta["created"])
        t_fill = parse_ts(mo["time"]) if mo else None
        db_to_tx_ms = None if t_fill is None else (t_fill - t_created).total_seconds() * 1000.0
        bar = bar_at(inst, t_fill or t_created)
        bid_c = ask_c = spread = None
        if bar:
            bid_c = float((bar.get("bid") or {}).get("c")) if (bar.get("bid") or {}).get("c") else None
            ask_c = float((bar.get("ask") or {}).get("c")) if (bar.get("ask") or {}).get("c") else None
            if bid_c and ask_c:
                spread = ask_c - bid_c
        atr = atr14(inst, t_fill or t_created)
        if side == "BUY":
            risk = fill - sl
            reward = tp - fill
            fill_delta = fill - xref
        else:
            risk = sl - fill
            reward = fill - tp
            fill_delta = xref - fill
        successful.append(
            {
                "cid": cid,
                "instrument": inst,
                "side": side,
                "xref": xref,
                "sl": sl,
                "tp": tp,
                "fill": fill,
                "stop_pips": sl_d / pip,
                "spread_pips": None if spread is None else spread / pip,
                "stop_over_spread": None if not spread else sl_d / spread,
                "atr14_m5": atr,
                "db_to_tx_ms": db_to_tx_ms,
                "fill_delta_pips": fill_delta / pip,
                "fill_risk_pips": risk / pip,
                "fill_reward_pips": reward / pip,
                "fill_r": None if risk <= 0 else reward / risk,
                "m1_bid_c": bid_c,
                "m1_ask_c": ask_c,
            }
        )

    # created_at from known table
    created = {c[0]: None for c in CANCELS}
    # filled from analysis caller; attach after
    payload = {
        "cancelled": cancelled,
        "successful": successful,
        "cancelled_stats": {
            "stop_pips": stats([x["stop_pips"] for x in cancelled]),
            "spread_pips": stats([x["m1_spread_pips"] for x in cancelled if x["m1_spread_pips"] is not None]),
            "stop_over_spread": stats(
                [x["stop_over_spread"] for x in cancelled if x["stop_over_spread"] is not None]
            ),
            "headroom_vs_m1_trigger_pips": stats(
                [
                    x["headroom_vs_m1_trigger_pips"]
                    for x in cancelled
                    if x["headroom_vs_m1_trigger_pips"] is not None
                ]
            ),
            "atr_pips": stats([x["atr_pips"] for x in cancelled if x["atr_pips"] is not None]),
            "sl_d_over_atr": stats(
                [x["sl_d_over_atr"] for x in cancelled if x["sl_d_over_atr"] is not None]
            ),
        },
        "successful_stats": {
            "stop_pips": stats([x["stop_pips"] for x in successful]),
            "spread_pips": stats(
                [x["spread_pips"] for x in successful if x["spread_pips"] is not None]
            ),
            "stop_over_spread": stats(
                [x["stop_over_spread"] for x in successful if x["stop_over_spread"] is not None]
            ),
            "db_to_tx_ms": stats(
                [x["db_to_tx_ms"] for x in successful if x["db_to_tx_ms"] is not None]
            ),
            "fill_delta_pips": stats([x["fill_delta_pips"] for x in successful]),
            "fill_r": stats([x["fill_r"] for x in successful if x["fill_r"] is not None]),
        },
        "candle_counts": {k: len(v) for k, v in candles.items()},
        "note": "M1 MBA candles are completed-bar bid/ask closes, not the live PricingInfo snapshot",
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("wrote", OUT.name)
    print("cancel stop_pips", payload["cancelled_stats"]["stop_pips"])
    print("success stop_pips", payload["successful_stats"]["stop_pips"])
    print("cancel spread", payload["cancelled_stats"]["spread_pips"])
    print("success spread", payload["successful_stats"]["spread_pips"])
    print("cancel stop/spread", payload["cancelled_stats"]["stop_over_spread"])
    print("success stop/spread", payload["successful_stats"]["stop_over_spread"])
    print("cancel trigger headroom pips", payload["cancelled_stats"]["headroom_vs_m1_trigger_pips"])
    for x in cancelled:
        print(
            x["instrument"],
            x["side"],
            "stop",
            round(x["stop_pips"], 2),
            "spr",
            None if x["m1_spread_pips"] is None else round(x["m1_spread_pips"], 2),
            "trigH",
            None
            if x["headroom_vs_m1_trigger_pips"] is None
            else round(x["headroom_vs_m1_trigger_pips"], 2),
            "atr",
            None if x["atr_pips"] is None else round(x["atr_pips"], 2),
        )


if __name__ == "__main__":
    main()

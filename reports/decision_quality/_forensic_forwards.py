"""Read-only M5 pull + forward returns + PG/reject extras for the forensic audit."""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SUM = Path(__file__).resolve().parent / "_forensic_summary.json"
OUT = Path(__file__).resolve().parent / "_forensic_extra.json"
PIP = {
    "EUR_USD": 0.0001,
    "GBP_USD": 0.0001,
    "AUD_USD": 0.0001,
    "USD_CAD": 0.0001,
    "USD_CHF": 0.0001,
    "USD_JPY": 0.01,
}


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


def parse_ts(raw: str | None):
    if not raw:
        return None
    s = str(raw).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
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
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def main() -> None:
    _load_dotenv()
    from forex_bot.oanda_client import _oanda_request, get_api, oanda_instrument
    import oandapyV20.endpoints.instruments as instruments

    summary = json.loads(SUM.read_text(encoding="utf-8"))
    trades = summary["completed_trades"]
    opened_times = [parse_ts(t["entry_time"]) for t in trades if t.get("entry_time")]
    api = get_api()
    candles = {}
    for sym in ("EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF"):
        r = instruments.InstrumentsCandles(
            instrument=oanda_instrument(sym),
            params={
                "granularity": "M5",
                "price": "M",
                "from": "2026-09-20T20:00:00.000000000Z",
                "to": "2026-09-21T21:30:00.000000000Z",
            },
        )
        data = _oanda_request(api, r, context=f"m5 {sym}")
        rows = []
        for c in data.get("candles") or []:
            mid = c.get("mid") or {}
            if not mid or not c.get("complete", True):
                continue
            rows.append(
                {
                    "time": parse_ts(c.get("time")),
                    "close": float(mid["c"]),
                }
            )
        candles[sym] = rows
        print(sym, "m5", len(rows))

    def fwd(sym, t0, side, mins):
        series = candles.get(sym) or []
        if not series or t0 is None:
            return None
        # first close at or after t0+mins
        target = t0 + timedelta(minutes=mins)
        future = None
        ref = None
        for row in series:
            if row["time"] <= t0:
                ref = row["close"]
            if row["time"] >= target:
                future = row["close"]
                break
        if future is None or ref is None:
            return None
        pip = PIP[sym]
        if side == "BUY":
            return (future - ref) / pip
        return (ref - future) / pip

    horizons = (5, 15, 30, 60)
    groups = defaultdict(list)
    for tr in trades:
        t0 = parse_ts(tr.get("entry_time"))
        side = tr.get("side")
        sym = tr.get("symbol")
        if not t0 or not side or not sym:
            continue
        for h in horizons:
            v = fwd(sym, t0, side, h)
            if v is None:
                continue
            groups[("all", h)].append(v)
            groups[(side, h)].append(v)
            groups[(tr.get("build"), h)].append(v)
            groups[(f"{sym} {side}", h)].append(v)

    def stats(xs):
        if not xs:
            return None
        xs = sorted(xs)
        mid = xs[len(xs) // 2] if len(xs) % 2 else 0.5 * (xs[len(xs) // 2 - 1] + xs[len(xs) // 2])
        return {
            "n": len(xs),
            "mean": sum(xs) / len(xs),
            "median": mid,
            "pos_rate": sum(1 for x in xs if x > 0) / len(xs),
        }

    fwd_out = {f"{k[0]}|{k[1]}m": stats(v) for k, v in groups.items()}

    # Rejection nearby fill displacement
    raw = json.loads((Path(__file__).resolve().parent / "_oanda_tx_20_21.json").read_text(encoding="utf-8"))
    fills = [
        t
        for t in raw["transactions"]
        if t.get("type") == "ORDER_FILL" and t.get("reason") == "MARKET_ORDER" and t.get("tradeOpened")
    ]
    rejs = summary["rejections"]
    rej_disp = []
    for r in rejs:
        rt = parse_ts(r.get("time"))
        nearby = []
        for t in fills:
            if t.get("instrument") != r.get("symbol"):
                continue
            ft = parse_ts(t.get("time"))
            if not rt or not ft:
                continue
            dt = abs((ft - rt).total_seconds())
            if dt <= 300:
                nearby.append((dt, t))
        nearby.sort(key=lambda x: x[0])
        item = {"reason": r["reason"], "symbol": r.get("symbol"), "side": r.get("side"), "nearby_n": len(nearby)}
        if nearby:
            t = nearby[0][1]
            fill = float(t.get("price"))
            sl = r.get("submitted_sl")
            tp = r.get("submitted_tp")
            mid = r.get("inferred_mid")
            item["nearest_fill_dt"] = nearby[0][0]
            item["nearest_fill"] = fill
            item["mid_to_fill"] = (fill - mid) if mid is not None else None
            if sl is not None and tp is not None and r.get("side") == "BUY":
                item["fill_vs_tp"] = tp - fill
                item["fill_vs_sl"] = fill - sl
            elif sl is not None and tp is not None:
                item["fill_vs_tp"] = fill - tp
                item["fill_vs_sl"] = sl - fill
        rej_disp.append(item)

    # TRADE_CLOSE market orders
    trade_closes = []
    for t in raw["transactions"]:
        if t.get("type") == "MARKET_ORDER" and t.get("reason") == "TRADE_CLOSE":
            keep = {k: t[k] for k in t if k not in ("accountID", "userID")}
            trade_closes.append(keep)

    extra = {
        "forward": fwd_out,
        "rejection_nearby": rej_disp,
        "trade_close_orders": trade_closes,
        "m5_counts": {k: len(v) for k, v in candles.items()},
    }
    OUT.write_text(json.dumps(extra, default=str), encoding="utf-8")
    print("wrote", OUT.name)


if __name__ == "__main__":
    main()

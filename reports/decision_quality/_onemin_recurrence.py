"""Read-only: new-build 45-90s close recurrence test. No OANDA writes."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DUMP = Path(__file__).resolve().parent / "_oanda_tx_20_21.json"
RECLASS = Path(__file__).resolve().parent / "_manual_close_reclass.json"
NEW_START = datetime(2026, 9, 21, 9, 40, 11, tzinfo=timezone.utc)
LO, HI = 45.0, 90.0

PG_PP = {
    "1589", "1597", "1621", "1661", "1669", "1681", "1689", "1697", "1705",
    "1657", "1721", "1745", "1785", "1809", "1803", "1825", "1841", "1855",
    "1883", "1901", "1909", "1925", "1933", "1941", "1953", "1961", "1969",
    "1977", "1985", "1993", "2001", "2009", "2017", "2025", "2033",
    "2129", "2143", "2213", "2223", "2251", "2297", "2301", "2317", "2357", "2361",
}
PG_SLTP = {"1629", "1607", "1643", "1617", "1731", "1869"}
MANUAL = {"2181", "2155", "2454", "2470"}


def parse_ts(s):
    if not s:
        return None
    t = str(s).replace("Z", "+00:00")
    if "." in t:
        head, rest = t.split(".", 1)
        frac = "".join(c for c in rest if c.isdigit())[:6].ljust(6, "0")
        tz = rest[len("".join(c for c in rest if c.isdigit())) :] or "+00:00"
        if tz.startswith("Z"):
            tz = "+00:00"
        t = f"{head}.{frac}{tz}"
    try:
        dt = datetime.fromisoformat(t)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _load_dotenv():
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


def pull_latest(have: set[str]) -> list[dict]:
    _load_dotenv()
    from oandapyV20.endpoints.accounts import AccountDetails
    import oandapyV20.endpoints.transactions as tx_ep
    from forex_bot.config import Config
    from forex_bot.oanda_client import _oanda_request, get_api

    api = get_api()
    aid = (Config.OANDA_ACCOUNT_ID or os.getenv("OANDA_ACCOUNT_ID") or "").strip()
    if api is None or not aid:
        return []
    acct = _oanda_request(api, AccountDetails(accountID=aid), context="account details")
    last_id = int(str((acct.get("lastTransactionID") or "0")).strip() or "0")
    max_have = max((int(i) for i in have if str(i).isdigit()), default=0)
    start = max(1, max_have - 5)
    req = tx_ep.TransactionIDRange(accountID=aid, params={"from": str(start), "to": str(last_id)})
    resp = _oanda_request(api, req, context="tx newer recurrence")
    txs = resp.get("transactions") or []
    print(f"last_id={last_id} newer={sum(1 for t in txs if str(t.get('id')) not in have)}")
    return txs


def main():
    dump = json.loads(DUMP.read_text(encoding="utf-8"))
    extra = json.loads(RECLASS.read_text(encoding="utf-8")) if RECLASS.exists() else {}
    by_id = {str(t.get("id")): t for t in (dump.get("transactions") or [])}
    for t in pull_latest(set(by_id)):
        by_id[str(t.get("id"))] = t
    txs = list(by_id.values())

    close_reasons = {
        "MARKET_ORDER_POSITION_CLOSEOUT",
        "MARKET_ORDER_TRADE_CLOSE",
        "STOP_LOSS_ORDER",
        "TAKE_PROFIT_ORDER",
    }
    rows = []
    for f in txs:
        if f.get("type") != "ORDER_FILL" or f.get("reason") not in close_reasons:
            continue
        if not (f.get("tradesClosed") or f.get("tradeReduced")):
            continue
        tc = (f.get("tradesClosed") or [{}])[0]
        tid = str(tc.get("tradeID") or "")
        entry = by_id.get(tid)
        et = parse_ts((entry or {}).get("time"))
        xt = parse_ts(f.get("time"))
        if not et or not xt or et < NEW_START:
            continue
        hold = (xt - et).total_seconds()
        mo = by_id.get(str(f.get("orderID") or "")) or {}
        rec = {
            "trade": tid,
            "fill": str(f.get("id")),
            "instrument": f.get("instrument"),
            "entry": et.isoformat(),
            "exit": xt.isoformat(),
            "hold": hold,
            "reason": f.get("reason"),
            "mo_reason": mo.get("reason"),
            "pl": float(str(tc.get("realizedPL") or f.get("pl") or 0) or 0),
        }
        rows.append(rec)

    print(f"\nNEW-BUILD completed exits n={len(rows)}")
    band = [r for r in rows if LO <= r["hold"] <= HI]
    print(f"NEW-BUILD 45-90s n={len(band)}")
    for r in sorted(rows, key=lambda x: x["hold"]):
        flag = " <45-90>" if LO <= r["hold"] <= HI else ""
        print(
            f"  {r['trade']:>6} {r['instrument']} hold={r['hold']:8.1f}s "
            f"{r['reason']} pl={r['pl']}{flag}"
        )

    bot, manual, unknown, sltp = [], [], [], []
    for r in band:
        if r["reason"] in ("STOP_LOSS_ORDER", "TAKE_PROFIT_ORDER"):
            sltp.append(r)
            continue
        if r["reason"] == "MARKET_ORDER_TRADE_CLOSE" or r["trade"] in MANUAL:
            manual.append(r)
            continue
        if r["reason"] == "MARKET_ORDER_POSITION_CLOSEOUT":
            if r["trade"] in PG_PP or r["trade"] in PG_SLTP:
                bot.append(r)
            else:
                unknown.append(r)
        else:
            unknown.append(r)

    print("\nBOT-INITIATED 45-90 (PG/log PositionClose):", len(bot), bot)
    print("MANUAL 45-90:", len(manual), manual)
    print("UNKNOWN 45-90 PositionClose:", len(unknown), unknown)
    print("BROKER SL/TP 45-90 (not recurrence):", len(sltp), sltp)


if __name__ == "__main__":
    main()

"""Read-only: post-23:00 entry geometry / reject / quote-time probe. No OANDA writes."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REJ = {"LOSING_TAKE_PROFIT", "STOP_LOSS_ON_FILL_LOSS", "TAKE_PROFIT_ON_FILL_LOSS"}
POST = "2026-09-21T22:00:04"


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


def main():
    _load_dotenv()
    from oandapyV20.endpoints.accounts import AccountDetails
    import oandapyV20.endpoints.transactions as tx_ep
    from forex_bot.config import Config
    from forex_bot.oanda_client import _oanda_request, get_api, fetch_pricing_snapshot
    from forex_bot.live_manage import quote_age_sec
    from forex_bot.entry_geometry import ENTRY_QUOTE_STALE_SEC
    import time

    api = get_api()
    aid = (Config.OANDA_ACCOUNT_ID or os.getenv("OANDA_ACCOUNT_ID") or "").strip()
    acct = _oanda_request(api, AccountDetails(accountID=aid), context="account")
    last_id = int(str(acct.get("lastTransactionID") or "0"))
    req = tx_ep.TransactionIDRange(accountID=aid, params={"from": "2470", "to": str(last_id)})
    txs = (_oanda_request(api, req, context="tx postdeploy") or {}).get("transactions") or []
    print(f"last_id={last_id} n={len(txs)}")

    by_id = {str(t.get("id")): t for t in txs}
    print("\n=== MARKET CLIENT_ORDER / CANCEL / FILL after 22:00Z ===")
    for t in txs:
        tt = str(t.get("time") or "")
        if tt < POST:
            continue
        typ = t.get("type")
        if typ not in {"MARKET_ORDER", "ORDER_FILL", "ORDER_CANCEL", "STOP_LOSS_ORDER", "TAKE_PROFIT_ORDER"}:
            continue
        ce = t.get("clientExtensions") or {}
        sl = t.get("stopLossOnFill") or {}
        tp = t.get("takeProfitOnFill") or {}
        if typ == "MARKET_ORDER" and t.get("reason") == "CLIENT_ORDER":
            print(
                f"  OPEN {t.get('id')} {tt} {t.get('instrument')} {t.get('units')} "
                f"tag={ce.get('tag')} slOnFill={sl.get('price')} tpOnFill={tp.get('price')}"
            )
        elif typ == "ORDER_CANCEL":
            print(
                f"  CANCEL {t.get('id')} {tt} reason={t.get('reason')} orderID={t.get('orderID')} "
                f"{t.get('instrument')}"
            )
        elif typ == "ORDER_FILL":
            opened = t.get("tradeOpened") or {}
            print(
                f"  FILL {t.get('id')} {tt} {t.get('instrument')} reason={t.get('reason')} "
                f"price={t.get('price')} pl={t.get('pl')} trade={opened.get('tradeID') or (t.get('tradesClosed') or [{}])[0].get('tradeID')}"
            )

    print("\n=== reject reasons in window ===")
    rejs = [t for t in txs if t.get("type") == "ORDER_CANCEL" and t.get("reason") in REJ and str(t.get("time") or "") >= POST]
    print("on_fill_rejects", len(rejs), [t.get("reason") for t in rejs])
    all_cancel = [t.get("reason") for t in txs if t.get("type") == "ORDER_CANCEL" and str(t.get("time") or "") >= POST]
    from collections import Counter
    print("all_cancel", Counter(all_cancel))

    print("\n=== live PricingInfo ages (one GET, compare to ENTRY 5s vs MANAGE 90s) ===")
    t0 = time.time()
    snap = fetch_pricing_snapshot(["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD", "USD_CHF"])
    t1 = time.time()
    print(f"http_rtt_approx={t1-t0:.3f}s now={t1:.3f} ENTRY_QUOTE_STALE_SEC={ENTRY_QUOTE_STALE_SEC}")
    for inst, q in snap.items():
        age = quote_age_sec(q, t1)
        print(
            f"  {inst} bid={q.bid} ask={q.ask} time_epoch={q.time_epoch} "
            f"age={None if age is None else round(age,3)}s "
            f"entry_ok={age is not None and age <= ENTRY_QUOTE_STALE_SEC} "
            f"manage_ok={age is not None and age <= 90}"
        )

    # attached SL/TP on filled trades via linked ON_FILL orders
    print("\n=== filled entries: fill vs attached SL/TP (R) ===")
    for t in txs:
        if t.get("type") != "ORDER_FILL" or t.get("reason") != "MARKET_ORDER" or not t.get("tradeOpened"):
            if str(t.get("time") or "") < POST:
                continue
        if t.get("type") != "ORDER_FILL" or not t.get("tradeOpened"):
            continue
        if str(t.get("time") or "") < POST:
            continue
        tid = str((t.get("tradeOpened") or {}).get("tradeID") or t.get("id"))
        fill = float(t.get("price"))
        inst = t.get("instrument")
        units = float(t.get("units") or 0)
        side = "BUY" if units > 0 else "SELL"
        sl = tp = None
        for u in txs:
            if u.get("type") in {"STOP_LOSS_ORDER", "TAKE_PROFIT_ORDER"} and str(u.get("tradeID")) == tid:
                if u.get("type") == "STOP_LOSS_ORDER":
                    sl = float(u.get("price"))
                else:
                    tp = float(u.get("price"))
        if sl is None or tp is None:
            print(f"  {tid} {inst} fill={fill} missing sl/tp")
            continue
        if side == "BUY":
            risk, reward = fill - sl, tp - fill
        else:
            risk, reward = sl - fill, fill - tp
        r = reward / risk if risk > 0 else None
        print(f"  {tid} {inst} {side} fill={fill} sl={sl} tp={tp} risk={risk:.5f} reward={reward:.5f} fill_r={r}")


if __name__ == "__main__":
    main()

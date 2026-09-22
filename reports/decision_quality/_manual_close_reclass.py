"""Read-only close attribution: OANDA dump + optional live GET of newer ids.

Never writes to OANDA. Strips accountID/userID from any saved output.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DUMP = Path(__file__).resolve().parent / "_oanda_tx_20_21.json"
OUT = Path(__file__).resolve().parent / "_manual_close_reclass.json"

# Proven deploy/restart UTC from Docker inspect + prior audit
NEW_MANAGE_START = datetime(2026, 9, 21, 9, 40, 11, tzinfo=timezone.utc)
RESTART_1141 = datetime(2026, 9, 21, 11, 41, 55, tzinfo=timezone.utc)
POST_2300 = datetime(2026, 9, 21, 22, 0, 4, tzinfo=timezone.utc)

# Known old-bug IDs from prior investigation (PG exit_reason + 61s cycle)
KNOWN_OLD_PP = {"1589", "1597", "1621"}
KNOWN_OLD_SLTP = {"1629"}


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


def parse_ts(s) -> datetime | None:
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


def strip_secrets(obj):
    if isinstance(obj, dict):
        return {
            k: strip_secrets(v)
            for k, v in obj.items()
            if k not in ("accountID", "userID", "homeConversionFactors")
        }
    if isinstance(obj, list):
        return [strip_secrets(x) for x in obj]
    return obj


def pull_newer(existing_ids: set[str]) -> list[dict]:
    _load_dotenv()
    from oandapyV20.endpoints.accounts import AccountDetails
    import oandapyV20.endpoints.transactions as tx_ep
    from forex_bot.config import Config
    from forex_bot.oanda_client import _oanda_request, get_api

    api = get_api()
    aid = (Config.OANDA_ACCOUNT_ID or os.getenv("OANDA_ACCOUNT_ID") or "").strip()
    if api is None or not aid:
        print("SKIP_PULL: no api")
        return []
    acct = _oanda_request(api, AccountDetails(accountID=aid), context="account details")
    last_id = int(str((acct.get("lastTransactionID") or "0")).strip() or "0")
    print(f"account_last_transaction_id={last_id}")
    max_have = max((int(i) for i in existing_ids if str(i).isdigit()), default=0)
    start = max(1, max_have - 20)
    collected = []
    end = last_id
    while end >= start:
        lo = max(start, end - 799)
        req = tx_ep.TransactionIDRange(
            accountID=aid, params={"from": str(lo), "to": str(end)}
        )
        resp = _oanda_request(api, req, context="tx idrange newer")
        txs = resp.get("transactions") or []
        collected.extend(txs)
        if lo == start:
            break
        end = lo - 1
    new = [t for t in collected if str(t.get("id") or "") not in existing_ids]
    print(f"pulled_newer n={len(new)} range={start}-{last_id}")
    return new


def summarize_order(t: dict) -> dict:
    ce = t.get("clientExtensions") or {}
    return {
        "id": str(t.get("id") or ""),
        "type": t.get("type"),
        "time": t.get("time"),
        "instrument": t.get("instrument"),
        "units": t.get("units"),
        "reason": t.get("reason"),
        "positionFill": t.get("positionFill"),
        "clientOrderID": t.get("clientOrderID"),
        "ce_id": ce.get("id") if isinstance(ce, dict) else None,
        "ce_tag": ce.get("tag") if isinstance(ce, dict) else None,
        "ce_comment": ce.get("comment") if isinstance(ce, dict) else None,
        "ce_keys": sorted(ce.keys()) if isinstance(ce, dict) else [],
        "has_tradeClose": bool(t.get("tradeClose")),
        "tradeClose": t.get("tradeClose"),
        "has_longUnits": t.get("longUnits") is not None or "longUnits" in t,
        "longUnits": t.get("longUnits"),
        "shortUnits": t.get("shortUnits"),
        "requestID": t.get("requestID"),
        "batchID": t.get("batchID"),
    }


def main() -> None:
    dump = json.loads(DUMP.read_text(encoding="utf-8"))
    txs = list(dump.get("transactions") or [])
    by_id = {str(t.get("id") or ""): t for t in txs}
    existing_ids = set(by_id)
    newer = pull_newer(existing_ids)
    for t in newer:
        by_id[str(t.get("id") or "")] = t
    all_txs = list(by_id.values())
    all_txs.sort(key=lambda t: int(str(t.get("id") or "0") or "0"))

    close_reasons = {
        "MARKET_ORDER_POSITION_CLOSEOUT",
        "MARKET_ORDER_TRADE_CLOSE",
        "STOP_LOSS_ORDER",
        "TAKE_PROFIT_ORDER",
    }
    fills = [
        t
        for t in all_txs
        if t.get("type") == "ORDER_FILL"
        and t.get("reason") in close_reasons
        and (t.get("tradesClosed") or t.get("tradeReduced"))
    ]

    # market orders linked to those fills
    close_orders = []
    for f in fills:
        oid = str(f.get("orderID") or "")
        mo = by_id.get(oid) or {}
        close_orders.append((f, mo))

    # All MARKET_ORDER with close-like reasons (even if fill missing)
    mo_close = [
        t
        for t in all_txs
        if t.get("type") == "MARKET_ORDER"
        and t.get("reason")
        in {"POSITION_CLOSEOUT", "TRADE_CLOSE", "MARKET_ORDER_POSITION_CLOSEOUT", "MARKET_ORDER_TRADE_CLOSE"}
    ]

    print("\n=== CLOSE MARKET_ORDER reasons ===")
    print(Counter(t.get("reason") for t in mo_close))
    print("=== CLOSE FILL reasons ===")
    print(Counter(t.get("reason") for t in fills))

    print("\n=== clientExtensions on close MARKET_ORDERs ===")
    for t in mo_close:
        s = summarize_order(t)
        print(
            f"{s['id']} {s['time']} {s['instrument']} reason={s['reason']} "
            f"ce_tag={s['ce_tag']!r} ce_id={s['ce_id']!r} cid={s['clientOrderID']!r} "
            f"posFill={s['positionFill']} tradeClose={s['has_tradeClose']} "
            f"long={s['longUnits']} short={s['shortUnits']}"
        )

    print("\n=== CLOSE FILLS with linked order CE ===")
    rows = []
    for f, mo in close_orders:
        ft = parse_ts(f.get("time"))
        opened = None
        tc = (f.get("tradesClosed") or [{}])[0] if f.get("tradesClosed") else {}
        tid = str((tc or {}).get("tradeID") or "")
        pl = float(str((tc or {}).get("realizedPL") or f.get("pl") or 0) or 0)
        entry_tx = by_id.get(tid)
        opened = parse_ts((entry_tx or {}).get("time")) if entry_tx else None
        hold = (ft - opened).total_seconds() if ft and opened else None
        s = summarize_order(mo) if mo else {}
        rec = {
            "fill_id": str(f.get("id") or ""),
            "order_id": str(f.get("orderID") or ""),
            "trade_id": tid,
            "instrument": f.get("instrument"),
            "time": f.get("time"),
            "oanda_reason": f.get("reason"),
            "pl": pl,
            "hold_sec": hold,
            "entry_time": (entry_tx or {}).get("time") if entry_tx else None,
            "units": f.get("units"),
            "mo_reason": s.get("reason"),
            "mo_ce_tag": s.get("ce_tag"),
            "mo_ce_id": s.get("ce_id"),
            "mo_clientOrderID": s.get("clientOrderID") or f.get("clientOrderID"),
            "mo_positionFill": s.get("positionFill"),
            "mo_has_tradeClose": s.get("has_tradeClose"),
            "mo_keys": sorted(mo.keys()) if mo else [],
            "fill_ce": (f.get("clientExtensions") or {}).get("tag")
            if isinstance(f.get("clientExtensions"), dict)
            else None,
            "fill_cid": f.get("clientOrderID"),
        }
        rows.append(rec)
        print(
            f"{rec['trade_id']:>6} fill={rec['fill_id']:>6} {str(rec['time'])[:19]} "
            f"{rec['instrument']} {rec['oanda_reason']} pl={rec['pl']} hold={rec['hold_sec']} "
            f"mo_reason={rec['mo_reason']} tag={rec['mo_ce_tag']!r} cid={rec['mo_clientOrderID']!r}"
        )

    # Window around restarts
    print("\n=== +/- 5 min around 09:40 / 11:41 / 22:00 UTC ===")
    bounds = [
        ("manage_fix", NEW_MANAGE_START),
        ("broker_exit_restart", RESTART_1141),
        ("post_2300", POST_2300),
    ]
    for name, center in bounds:
        print(f"\n-- {name} {center.isoformat()} --")
        for t in all_txs:
            dt = parse_ts(t.get("time"))
            if not dt:
                continue
            delta = (dt - center).total_seconds()
            if abs(delta) > 300:
                continue
            if t.get("type") not in {
                "MARKET_ORDER",
                "ORDER_FILL",
                "ORDER_CANCEL",
                "STOP_LOSS_ORDER",
                "TAKE_PROFIT_ORDER",
            }:
                continue
            ce = t.get("clientExtensions") or {}
            print(
                f"  {delta:+7.1f}s id={t.get('id')} type={t.get('type')} "
                f"reason={t.get('reason')} {t.get('instrument')} "
                f"tag={ce.get('tag') if isinstance(ce, dict) else None} "
                f"cid={t.get('clientOrderID')}"
            )

    # post-23:00 all fills
    print("\n=== ALL txs after 21:50Z (pre-flatten + post-2300) ===")
    for t in all_txs:
        dt = parse_ts(t.get("time"))
        if not dt or dt < datetime(2026, 9, 21, 21, 50, tzinfo=timezone.utc):
            continue
        ce = t.get("clientExtensions") or {}
        print(
            f"  {t.get('time')} id={t.get('id')} type={t.get('type')} "
            f"reason={t.get('reason')} {t.get('instrument')} "
            f"tag={ce.get('tag') if isinstance(ce, dict) else None} "
            f"cid={t.get('clientOrderID')} pl={t.get('pl')}"
        )

    OUT.write_text(
        json.dumps(
            {
                "pulled_at": datetime.now(timezone.utc).isoformat(),
                "n_txs": len(all_txs),
                "n_close_fills": len(rows),
                "close_fills": strip_secrets(rows),
                "close_market_orders": [summarize_order(t) for t in mo_close],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {OUT.name}")


if __name__ == "__main__":
    main()

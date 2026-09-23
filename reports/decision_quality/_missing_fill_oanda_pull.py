"""READ-ONLY OANDA pull for missing-orderFillTransaction forensic.

GET AccountDetails, TransactionIDRange, OpenPositions, OrdersPending only.
Never creates, cancels, or replaces orders.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent / "_missing_fill_oanda_tx.json"


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


def main() -> None:
    _load_dotenv()
    from oandapyV20.endpoints.accounts import AccountDetails
    import oandapyV20.endpoints.orders as orders
    import oandapyV20.endpoints.positions as positions
    import oandapyV20.endpoints.transactions as tx_ep

    from forex_bot.config import Config
    from forex_bot.oanda_client import _oanda_request, get_api

    api = get_api()
    aid = (Config.OANDA_ACCOUNT_ID or os.getenv("OANDA_ACCOUNT_ID") or "").strip()
    if api is None or not aid:
        raise SystemExit("OANDA API or account id unavailable")

    acct = _oanda_request(api, AccountDetails(accountID=aid), context="account details")
    last_id = int(str((acct.get("lastTransactionID") or "0")).strip() or "0")
    start = max(1, last_id - 199)
    req = tx_ep.TransactionIDRange(
        accountID=aid,
        params={"from": str(start), "to": str(last_id)},
    )
    resp = _oanda_request(api, req, context="tx idrange")
    txs = resp.get("transactions") or []
    open_pos = _oanda_request(
        api, positions.OpenPositions(accountID=aid), context="open positions"
    )
    pending = _oanda_request(api, orders.OrdersPending(accountID=aid), context="pending orders")
    payload = {
        "pulled_at_utc": datetime.now(timezone.utc).isoformat(),
        "account_last_transaction_id": last_id,
        "range_from": start,
        "range_to": last_id,
        "transaction_count": len(txs),
        "transactions": txs,
        "positions": open_pos.get("positions") if isinstance(open_pos, dict) else None,
        "pending_orders": pending.get("orders") if isinstance(pending, dict) else None,
        "note": "READ-ONLY GETs only; no OrderCreate/PositionClose/TradeCRC",
    }
    OUT.write_text(json.dumps(payload), encoding="utf-8")
    print(f"wrote {OUT.name} n={len(txs)} last_id={last_id} from={start}")


if __name__ == "__main__":
    main()

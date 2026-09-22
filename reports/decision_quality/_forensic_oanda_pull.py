"""Read-only OANDA transaction pull for the 20-21 Sep 2026 forensic audit.

GET only. Never creates, cancels, or replaces orders.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent / "_oanda_tx_20_21.json"


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
    import oandapyV20.endpoints.transactions as tx_ep

    from forex_bot.config import Config
    from forex_bot.oanda_client import _oanda_request, get_api

    api = get_api()
    aid = (Config.OANDA_ACCOUNT_ID or os.getenv("OANDA_ACCOUNT_ID") or "").strip()
    if api is None or not aid:
        raise SystemExit("OANDA API or account id unavailable")

    acct = _oanda_request(api, AccountDetails(accountID=aid), context="account details")
    last_id = int(str((acct.get("lastTransactionID") or "0")).strip() or "0")
    pages = []
    # Walk backward in 800-id chunks until before 2026-09-20 19:00Z or id 1.
    end = last_id
    collected: list[dict] = []
    while end >= 1:
        start = max(1, end - 799)
        req = tx_ep.TransactionIDRange(
            accountID=aid,
            params={"from": str(start), "to": str(end)},
        )
        resp = _oanda_request(api, req, context="tx idrange")
        txs = resp.get("transactions") or []
        pages.append({"from": start, "to": end, "n": len(txs)})
        if not txs:
            break
        collected.extend(txs)
        first_time = str(txs[0].get("time") or "")
        if first_time and first_time < "2026-09-20T18:00:00":
            break
        if start == 1:
            break
        end = start - 1

    # Keep a slightly wider window then filter in analysis.
    payload = {
        "pulled_at_utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        "account_last_transaction_id": last_id,
        "pages": pages,
        "transaction_count": len(collected),
        "transactions": collected,
    }
    OUT.write_text(json.dumps(payload), encoding="utf-8")
    print(f"wrote {OUT.name} n={len(collected)} last_id={last_id} pages={pages}")


if __name__ == "__main__":
    main()

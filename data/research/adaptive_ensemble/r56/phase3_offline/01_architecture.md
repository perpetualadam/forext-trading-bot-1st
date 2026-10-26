# R.56 phase 3 architecture

The collector is a separate program under `phase3_offline`. It does not start `main.py` and it does not import `forex_bot`.

`collector_main.py` accepts only `python collector_main.py --offline`. Any other argument, including a missing `--offline`, returns exit code 2. There is no live, connect, or authenticate branch.

## Request plan

`readonly_request_plan.py` builds exactly two candidates, in this order:

1. `GET /v3/accounts/{accountID}/summary` with an empty query.
2. `GET /v3/accounts/{accountID}/pricing` with query key `instruments` only.

The instrument list is the production default, in that order: `EUR_USD`, `GBP_USD`, `USD_JPY`, `AUD_USD`, `USD_CAD`, `USD_CHF`. The account id argument must be the synthetic constant. A different id is rejected and is not echoed.

The plan does not add candles, orders, trades, positions, transactions, financing, instrument metadata, or `includeHomeConversions`.

## Gate

`readonly_request_gate.py` checks every candidate before a transport is used. The checks are host `api-fxtrade.oanda.com`, port `443`, scheme `https`, method `GET`, no body, redirects false, retries `0`, stream false, and the two path patterns above. An extra candidate key, including an `approved` flag, is rejected. Pricing is rejected unless it is step 2 after summary. Step 3 is rejected.

The object returned to the transport replaces the path with `/v3/accounts/{accountID}/summary` or `/v3/accounts/{accountID}/pricing`. The synthetic account id is not in that object.

## Transport and session

`offline_transport.py` has one class, `SyntheticTransport`. `live_transport()` raises `LIVE_TRANSPORT_NOT_AVAILABLE` and does not construct a client.

`collector_session.py` approves the summary, executes it, and passes the dictionary to the Phase 2 account adapter. Pricing runs only when that adapter returns `DIAGNOSTIC_RECORDED`. The pricing dictionary then goes to the Phase 2 pricing adapter. One JSON file is written at the end. A rejected summary or pricing record uses `SESSION_INCOMPLETE`.

The session status `SESSION_COMPLETE_SYNTHETIC` means both synthetic responses were accepted by the Phase 2 adapters. It does not mean the account, pip value, financing, or an executable size has been verified.

# Future authenticated diagnostic session

This phase does not authorise that session. No credential reader and no live transport were created.

## Minimum later steps

1. A new written authorisation for one authenticated diagnostic process, naming practice or live explicitly. This offline gate allows only the host string `api-fxtrade.oanda.com` and rejects the practice host. A practice session cannot reuse this gate unchanged.
2. Keep the process out of `main.py`. Do not import `forex_bot.app`, `bot_loop`, `trading`, `execution`, or `oanda_exec`.
3. Add a transport that can perform only the two descriptions this gate has already approved. It must still reject every other method, path, host, and a third request before a socket is created.
4. Pass copies of the raw summary dictionary and the raw pricing dictionary into the existing Phase 2 `build` functions. Do not log the account id, token, or raw document.
5. Do not add `includeHomeConversions`, an instruments request, or candles in that first authenticated run unless a separate authorisation changes the plan.
6. Do not treat a completed diagnostic file as permission to calculate an executable size or to place an order.

## Why the production client is not that transport

`forex_bot/oanda_client.py` `build_api` (lines 104–126) creates one `oandapyV20.API` from the configured token. Importing that module imports `forex_bot.config`, which loads the environment file. `oanda_exec.py` uses `get_api()` for `OrderCreate` at line 504 and for position close at line 423. The same object can read and change the account.

`fetch_account_summary` (lines 140–194) and `fetch_pricing_snapshot` (lines 503–584) are the two reads this plan copies. Their raw dictionaries stay inside those functions today. A future collector should pass copies of those dictionaries to Phase 2. It should not start the lifespan that also runs `run_bot`.

Until the write helpers are unreachable from the diagnostic process, `DATA_ONLY_MODE_NOT_PROVEN_SAFE` remains the production classification.

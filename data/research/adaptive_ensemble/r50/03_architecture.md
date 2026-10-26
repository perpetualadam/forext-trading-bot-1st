# Standalone connector

`connector.py` loads `data/research/adaptive_ensemble/r48/readonly_transport.py` with `importlib`. It uses the standard library only. It does not import `forex_bot`, read an environment variable, open a socket, or call an HTTP library.

The future allowlist, enforced by the R.48 path builder, is:

- GET `https://api-fxtrade.oanda.com/v3/accounts/{accountID}/instruments`
- GET `https://api-fxtrade.oanda.com/v3/accounts/{accountID}/pricing`

Pricing includes `includeHomeConversions=true`. Both calls filter the same six instruments. Orders, trades, positions, summaries, discovery, transactions, candles, historical prices, and streams are rejected before a transport is called.

Each prepared call is GET, has a five-second timeout, zero retries, redirects disabled, no body, and no stream. The host is the fixed live v20 host. An extra keyword such as a URL, body, or stream flag raises `R50_REJECTED` before the transport.

`run_synthetic` performs exactly two transport calls, instruments then pricing. A non-200 status or a transport exception stops the lifecycle. There is no second attempt and no redirect follow.

`launch` ignores its arguments, does not print them, prints that live verification remains unauthorised, and returns 0. `enable_live` always raises `R50_LIVE_ACCESS_DISABLED`. Real credential collection is not implemented.

The public document is leak-checked for the synthetic account identifier, the synthetic token, `Bearer`, `Authorization`, `https://`, and the shadow fallback `1.35`. Exception text is the fixed code `R50_REJECTED` or `R50_LIVE_ACCESS_DISABLED`.

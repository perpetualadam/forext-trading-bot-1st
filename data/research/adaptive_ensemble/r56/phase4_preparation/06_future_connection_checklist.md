# Future diagnostic session checklist

This list is documentation. None of these steps is authorised now, and none of them is implemented as a live path.

`TARGET_ENVIRONMENT = OANDA_LIVE`

`LIVE_NETWORK_ACCESS = NOT_AUTHORISED`

A future session would need a new written authorisation that names the environment. The Phase 3 gate rejects the practice host. A practice session cannot reuse this gate unchanged. Silently switching this constant to practice is not permitted.

Before any credential is accessed, the operator would confirm that the program will send only:

1. `GET https://api-fxtrade.oanda.com:443/v3/accounts/{accountID}/summary`
2. `GET https://api-fxtrade.oanda.com:443/v3/accounts/{accountID}/pricing?instruments=EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF`

No other query key. No body. No redirect. No retry. No third request. No orders, trades, positions, candles, financing, or account changes.

Further conditions that are not met:

- The process must not import `app`, `bot_loop`, `trading`, `execution`, `oanda_exec`, `paper_broker`, or `live_broker`.
- The production `oanda_client` is not this transport. `build_api` loads a token, and the same client family is used for order and close paths.
- Copies of the two response documents would be passed into the existing Phase 2 adapters. Phase 2 and Phase 3 would stay unmodified.
- `includeHomeConversions` and an instruments metadata request need their own authorisation. They are not added here.
- A completed diagnostic file is not permission to size, stake, or send an order.
- A real token may still have trading authority. GET-only HTTP in this candidate does not remove that authority from a token.
- The 5.0 s and 15.0 s budgets are not a proven wall-clock deadline for DNS, TLS, or a socket. That requirement is still open.
- Real credentials remain unauthorised. Authenticated OANDA requests remain unauthorised.

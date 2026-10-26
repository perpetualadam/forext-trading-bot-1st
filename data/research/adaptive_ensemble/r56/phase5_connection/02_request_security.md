# R.56 Phase 5 request security

`TARGET_ENVIRONMENT = OANDA_LIVE`

`LIVE_NETWORK_ACCESS = NOT_AUTHORISED`

The public transport has two methods. There is no `send_request`, no method argument, and no URL argument.

## Allowed operations

1. `GET https://api-fxtrade.oanda.com:443/v3/accounts/{accountID}/summary` with an empty query.
2. `GET https://api-fxtrade.oanda.com:443/v3/accounts/{accountID}/pricing` with `instruments=EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF`.

The account id is accepted only when it equals the pinned synthetic id. It is then placed into a fixed path. Any other id, including another well-formed id, raises `REAL_ACCOUNT_ID_REJECTED`. The stored endpoint uses `{accountID}`.

## Independent checks

`validate_outbound` runs inside the transport, in addition to the unchanged Phase 3 gate.

- Method other than GET, including POST, PUT, PATCH, and DELETE, is `METHOD_REJECTED`.
- `http`, another host, or another port is rejected. The practice host is rejected.
- `/orders`, `/trades`, `/positions`, transactions, candles, financing, configuration, and instrument metadata are `ACCOUNT_CHANGING_REJECTED`.
- A body, a redirect, a retry, a stream, an extra query key, `includeHomeConversions`, or a short instrument list is rejected.
- A third child start is `REQUEST_LIMIT`. Pricing without a completed summary is `SEQUENCE_REJECTED`. A summary failure does not start the pricing child.
- TLS must be `CERT_REQUIRED` with hostname checks. `disable_tls_verification` raises `TLS_VERIFICATION_CANNOT_BE_DISABLED`.
- `open_live_connection` raises `LIVE_NETWORK_NOT_AUTHORISED` before `HTTPSConnection`.
- The child environment copies a small set of Windows process keys. `HTTP_PROXY` and `HTTPS_PROXY` are not copied. The connector flag `proxy_from_environment` is rejected.
- Responses over `1,048,576` bytes are `RESPONSE_TOO_LARGE` and are not parsed. Non-200 responses are not copied into the result.

An in-process TLS context check does not show how a live server certificate would validate.

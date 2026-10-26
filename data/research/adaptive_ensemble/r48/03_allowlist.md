# R.48 endpoint and method allowlist

The live host named in `official_rest_host` for a live mode is `api-fxtrade.oanda.com`. The reported environment is Live, so the practice host is rejected. No request was sent to either host.

Permitted shape, not executed:

| Method | Host | Path pattern | Query |
| --- | --- | --- | --- |
| GET | `api-fxtrade.oanda.com` | `/v3/accounts/{accountID}/instruments` | `instruments` equal to the six names |
| GET | `api-fxtrade.oanda.com` | `/v3/accounts/{accountID}/pricing` | the same six names, plus `includeHomeConversions=true` |

The account identifier is a path input to a future isolated process. It is not written in source or evidence. The stored description uses `{accountID}`.

Rejected by the gate: POST, PUT, PATCH, DELETE, the practice host, any other host, redirects, retries, request bodies, streams, and these paths: orders, summary, candles, pricing stream, transactions, positions, trades, account listing, and instrument candle history. Timeout is 5 seconds. Redirect status codes are refused and not followed. HTTP other than 200 is refused.

Pricing would be one snapshot of the six names, not a stream. The six names are EUR_USD, GBP_USD, AUD_USD, USD_CAD, USD_CHF, and USD_JPY.

# R.49 future endpoint allowlist

Not called in this stage.

| Method | Host | Path pattern | Query |
| --- | --- | --- | --- |
| GET | `api-fxtrade.oanda.com` | `/v3/accounts/{accountID}/instruments` | the six names only |
| GET | `api-fxtrade.oanda.com` | `/v3/accounts/{accountID}/pricing` | the six names, plus home conversions |

The six names are EUR_USD, GBP_USD, AUD_USD, USD_CAD, USD_CHF, and USD_JPY.

The account identifier stays in memory for the path check. It is not written in this file as a real value. Evidence uses `{accountID}`.

The runner rejects other methods, other hosts, other paths, redirects, retries, bodies, and streams by calling the R.48 gate. The network send itself is absent. Timeout on the plan is 5 seconds. `NETWORK_EXECUTION` is false, so a confirmation phrase still does not connect.

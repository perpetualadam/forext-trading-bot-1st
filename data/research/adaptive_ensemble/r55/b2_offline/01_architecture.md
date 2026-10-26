# Offline architecture

This directory is an offline candidate for a future Option A session. It is not a live connector. No module in this directory imports `socket`, `http.client`, `urllib`, or a production module.

## Components

`request_plan.py` builds two request descriptions and rejects anything else. The host is `api-fxtrade.oanda.com`, the port is 443, and the method is GET. The paths are `/v3/accounts/{accountID}/instruments` and `/v3/accounts/{accountID}/pricing`. The instruments query has only `instruments`. The pricing query adds only `includeHomeConversions=true`. The account identifier is checked and then left out of the description. There is no third description. Summary, orders, trades, positions, transactions, and candles are rejected. POST, PUT, PATCH, DELETE, another host, another port, another query key, a body, streaming, redirects, and retries are rejected.

`response_validation.py` reads bytes or objects the caller already has. It classifies 401, 403, 404, 429, and 5xx without reading those bodies. A 200 body larger than 1,048,576 bytes is `RESPONSE_TOO_LARGE`. Invalid JSON is `MALFORMED_JSON`. The six names must all be present. An unexpected name, a missing name, a missing pip location, a non-finite or non-positive price, and a bid above the ask are `SCHEMA_REJECTED`. A missing timestamp is `MISSING_TIMESTAMP`. A timestamp that is not `YYYY-MM-DDTHH:MM:SS` with optional fractions and `Z` or a numeric offset is `MALFORMED_TIMESTAMP`. No age limit is applied. `tradeable` false is rejected as not a usable quote. Missing conversion fields stay `NOT_RETURNED`. More than one home-conversion currency is `AMBIGUOUS`. Neither case sets the account home currency.

`synthetic_session.py` runs only the built-in fixtures on the normal path. `launch` with no arguments, or with any argument other than exact `--offline` or exact `--live`, prints the disabled sentence and returns. Exact `--live` prints the live-disabled sentence and does not call `run_live`. `run_live` raises `R55B2_LIVE_DISABLED` and has no further statements. `run_offline` accepts no transport class. `run_session` rejects a live mode and any injected class before that class is constructed. `run_test_case` accepts synthetic status and body records for tests. `launch` and `run_offline` do not call it. It is not a sandbox.

## Future limits, not a live client

`FUTURE_LIMITS` records requirements for a later design. Credential entry, hidden token entry, and TLS are marked required or not implemented. The per-request timeout value is 5.0 seconds. The separate total-session ceiling is 15.0 seconds, enough on paper for two 5-second requests plus local work. `timeout_enforcement` is `NOT_IMPLEMENTED_OFFLINE`. Nothing in this directory sleeps, opens a socket, or applies that ceiling to a connection. Whether 5 seconds suits the broker remains unverified.

## Output

A successful offline run writes `synthetic_output.json` beside the executable. The file is fixture output. A failed run deletes the designated file first, so a stale success file does not remain. The file is written only when both responses validate.

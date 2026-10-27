# First request specification — NOT EXECUTABLE OR AUTHORISED

- Environment: LIVE; host: `api-fxtrade.oanda.com`; method: GET.
- Path: `/v3/instruments/EUR_USD/candles`.
- `from=2026-09-02T10:00:00Z`.
- `to=2026-09-02T10:49:59Z`.
- `granularity=M5`, `price=MBA`, `smooth=false`, `includeFirst=true`.
- Count omitted; no additional query parameters.
- Future fixed headers only: bearer Authorization supplied in memory,
  Accept-Datetime-Format RFC3339, Accept application/json, Accept-Encoding identity.
- No proxy, redirect, alternate instrument/host, account identifier, account
  endpoint, order/trade/position operation, retry, pagination or polling.
- One separately reviewed native session; at most one attempted request;
  proposed total budget 15 s including cleanup, subject to deadline limitations.

No command, actual credential or executable request is supplied.

## Boundary acceptance

The proposed to=end−1 second convention remains unproven. Start-filtering and
completion-filtering interpretations can produce different counts. Do not assert
exactly ten candles or silently change the interval. A changed provider contract
requires a revised specification before approval.

Validate HTTP status/content type, exact instrument/M5 schema, RFC3339 timestamps,
unique ordered in-range M5 candle starts, completion flags, finite positive MBA
OHLC, valid OHLC relationships and uncrossed bid/ask. Incomplete candles are
reported/excluded, not repaired. Record actual observed complete count, gaps,
raw hash and normalised hash. Nine/ten/empty/incomplete synthetic responses are
tested; structural acceptance of an empty response is not proof of useful market
data acquisition. Never fabricate missing candles or infer market closure.

Redirects, HTTP errors, malformed/out-of-range response, timeout or ambiguous
outcome consume any claimed session without another request. Remote receipt
cannot be established from local timeout. No request has been made.

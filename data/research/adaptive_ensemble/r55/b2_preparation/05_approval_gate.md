# Approval gate

Boundary B2 is not approved. This preparation does not open the gate.

## What must be reviewed before any authenticated request

An independent review of this `b2_preparation` directory, plus a new written user approval, would be required before any implementation. The approval would have to say, in substance, all of the following:

1. The approved design is Option A: at most two sequential GET requests, instruments then pricing, for the six named pairs, with `includeHomeConversions=true` only on pricing.
2. Option B is not included. An account-summary request needs its own later approval after local schema documentation exists.
3. The approval names the new executable hash after that executable is built and offline-tested. The B1 hash `af9a93edc6779298f819430062e34b48289fced922d65f24a1d62a0982be8a90` is not an approval to connect.
4. The session is one local run. It shows the confirmation screen, waits for exact `CONFIRM PREVIEW`, then asks for the account identifier and a hidden token. It does not read `.env` or a credential store.
5. Output is sanitised. Evidence class for a real parse would be `READ_ONLY_RESPONSE_NOT_ACCOUNT_VERIFIED`. `ACCOUNT_VERIFIED` is not granted. Home currency, stake mapping, token permission, and executable size stay unresolved unless that same approval identifies a specific new field, which this gate does not.
6. No order, trade, position change, candle download, stream, backtest, strategy activation, or production deployment is included.

Until that approval exists, implementation is not authorised and the request is not authorised.

## What this gate does not accept as approval

- A PASS on this preparation.
- A passing offline test.
- HTTP 200 on a future response.
- Parser acceptance.
- The R.46 screen, the R.47 ticket, or the historical financing panel.
- A token typed into chat, a command line, or a file.
- An environment variable or a module flag.

## Current closures that stay in force

- B1 `--live` prints the disabled sentence and does not call `run_live`.
- `run_live()` raises `R55B1_LIVE_NOT_SELECTED` before a prompt or a client.
- `run_session(mode="live")` raises that code before callbacks.
- The normal B1 executable accepts only `SyntheticTransport`.
- `run_test_session` is not a live entry and not a sandbox.
- R.48 `perform_request` still raises `R48_AUTHENTICATED_EXECUTION_BLOCKED`.

## Stop line

Authenticated OANDA GET requests: NOT AUTHORISED.

Practice orders: NOT AUTHORISED.

Live trading: NOT AUTHORISED.

Production deployment: NO-GO.

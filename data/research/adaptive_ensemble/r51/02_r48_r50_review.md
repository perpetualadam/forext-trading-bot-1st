# R.48–R.50 integration

R.51 loads the R.50 connector and the R.48 gate by file path. It does not edit either stage.

## Allowlist

R.48 allows GET on `api-fxtrade.oanda.com` for `/v3/accounts/{accountID}/instruments` and `/v3/accounts/{accountID}/pricing` only. The instrument filter is EUR_USD, GBP_USD, AUD_USD, USD_CAD, USD_CHF, USD_JPY. Pricing adds `includeHomeConversions=true`. `perform_request` still raises `R48_AUTHENTICATED_EXECUTION_BLOCKED`.

## R.50 workflow

`run_synthetic` prepares those two GET calls and parses an injected transport result. Absent fields become `NOT_RETURNED`. A name outside the six fails closed. After the R.50 correction, conversion availability is `PRESENT` only when a factor value was returned. Removing both conversion objects leaves every factor `NOT_RETURNED` and does not insert 1.35.

## Network default

R.50 `launch` prints that live verification remains unauthorised and returns. `enable_live` raises `R50_LIVE_ACCESS_DISABLED` for every argument. R.51 keeps that default: its own `launch` prints the same refusal, and passing `http.client.HTTPSConnection` into the session raises `R51_LIVE_TRANSPORT_DISABLED` before that class is called.

## Credential handoff

R.49 can parse injected values and still refuses the network, including after its confirmation phrase. Hidden prompting is not called. R.51 does not add a prompt. `future_credential_entry` raises the disabled code and reads nothing.

## Manual procedure

R.50 told the user not to type a token and not to edit the connector to force a connection. R.51 keeps that instruction. The future live entry point is not in this stage.

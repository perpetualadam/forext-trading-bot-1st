# R.48 and R.49 integration review

R.50 reads the R.48 gate by file path. It does not edit R.48 or R.49, and it does not import a production package.

## R.48 method and endpoint restrictions

`readonly_transport.py` allows one host, `api-fxtrade.oanda.com`, and two kinds, `instruments` and `pricing`. The instrument filter is the six names EUR_USD, GBP_USD, AUD_USD, USD_CAD, USD_CHF, and USD_JPY. Pricing is specified with `includeHomeConversions=true`. Any other kind fails inside `build_path` before a path is returned. Practice hosts are outside the allowlist.

## R.48 authentication gate

`EXECUTION_PERMITTED` is false. `perform_request` always raises `R48_AUTHENTICATED_EXECUTION_BLOCKED`. R.48 therefore does not provide a working authenticated connector. R.50 does not call `perform_request`.

## R.48 response sanitisation

The parser requires the expected list shape, drops unexpected keys, and stores absent fields as `MISSING`. It keeps positive-units and negative-units factors apart, and it keeps account-gain and account-loss factors apart. A spread is derived from the instrument `pipLocation`. R.50 maps `MISSING` to `NOT_RETURNED` and rejects a name outside the six.

## R.49 handoff

`handoff_runner.py` can parse injected synthetic payloads and write a sanitised plan. Its public result uses `planned_calls`. Hidden prompting exists in the module and is not called by `main`.

## R.49 network gate

`NETWORK_EXECUTION` is false. `arm_network` rejects a bad phrase and, with the prepared confirmation phrase, still raises `R49_NETWORK_GATE_CLOSED`. A normal launch prints that the gate is closed and returns without asking for a credential. Extra arguments are rejected and are not echoed.

## What R.50 adds

R.50 is the standalone workflow that prepares the two GET calls, accepts only an injected transport, parses both payloads, and emits a `SYNTHETIC_TEST_ONLY` matrix. `enable_live` raises `R50_LIVE_ACCESS_DISABLED` for every argument. No flag, environment variable, phrase, or constant in this stage opens a socket.

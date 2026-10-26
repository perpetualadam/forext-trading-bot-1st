# R56_PHASE4_AUTHENTICATED_DIAGNOSTIC_PREPARATION_REPORT

Overall: **PASS**

`TARGET_ENVIRONMENT = OANDA_LIVE`

`LIVE_NETWORK_ACCESS = NOT_AUTHORISED`

Real OANDA access remains unauthorised. This phase implemented and tested an offline candidate. It did not connect to OANDA, did not read a real credential, did not start the bot, and did not enable a live entry point.

## Architecture

The candidate lives only in `data/research/adaptive_ensemble/r56/phase4_preparation/`. `offline_entry.launch` accepts `["--offline"]` and runs `diagnostic_session.run_offline` against `synthetic_transport.OfflineDouble`. The session reuses the Phase 3 request gate and the Phase 2 `build` and `stamp` adapters by file path. Phase 2 `write_record` stays on its own log directory. Phase 2 and Phase 3 files were not modified.

## Request allowlist

1. `GET /v3/accounts/{accountID}/summary` with an empty query.
2. `GET /v3/accounts/{accountID}/pricing` with `instruments=EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF`.

Host `api-fxtrade.oanda.com`, port `443`, scheme `https`, method `GET`, no body, no redirect, no retry, no stream, maximum two requests, stop on the first failure, maximum `1,048,576` bytes. The logged path uses `{accountID}`.

## Credentials

Only `SyntheticCredential` with classification `SYNTHETIC_TEST_ONLY` and token prefix `SYNTHETIC-TOKEN-R56P4-`. `read_real_credential()` raises `REAL_CREDENTIAL_INPUT_NOT_AUTHORISED`. `HIDDEN_INPUT = NOT_IMPLEMENTED`. Tokens, account identifiers, and raw exception text are not written. An operator confirmation of the two GET requests, before any future credential access, is described in `06_future_connection_checklist.md` and is not implemented.

## Timeouts

Deadlines are enforced on the offline phase interface. A 30 s cooperative stall stops at injected clock `5.0001` with `REQUEST_DEADLINE`. A session jump to `15.0000` stops pricing with `SESSION_DEADLINE` and does not wait 15 wall seconds. A slow body stopped at `0.3001`.

A non-cooperative `0.20` s sleep against a `0.05` s budget was not preempted. Measured wall time `0.2182` s, `observed_wall_seconds` `0.2005`, phases `connect` only, then `REQUEST_DEADLINE`. `live_socket_timeout = NOT_EXERCISED`. This does not solve a blocking DNS, TLS, or socket operation.

## Tests

`24 passed, 0 failed, 0 skipped, 0.53 s`.

Network blocking remained active. No production import. No order-changing request.

## Example sanitised synthetic output

Session `r56-fe35d43a3c3c4cd5b78cf01be514b2a0`, schema `r56.phase4.1`, collected `2026-10-22T13:00:00Z`.

- `data_source`: `SYNTHETIC_TEST_ONLY`
- `target_environment`: `OANDA_LIVE`
- `live_network_access`: `NOT_AUTHORISED`
- `session_status`: `SESSION_COMPLETE_SYNTHETIC`
- `broker_evidence_complete`: `false`
- `account_identity_verified`: `false`
- Fixture currency `GBP`, balance `100.00`, NAV `100.00`, margin available `100.00`. `home_currency_source` is `BROKER_REPORTED` because the synthetic field was present. It is not a live account confirmation.
- EUR_USD bid `1.10000`, ask `1.10020`, spread `0.00020`, quote time `2026-10-21T16:00:00Z`, tradeable `true`, spread pips `NOT_CALCULATED`, home conversion `HOME_CONVERSION_NOT_VERIFIED`.
- The other five instruments are in the same log, with the same unresolved markers.
- `executable_order`: `NOT_PRODUCED`
- `gbp_conversion_fallback`: `NOT_USED`
- Missing: quote freshness, GBP pip value, stake-to-unit mapping, financing, pip location, home conversion.

The account identifier and the synthetic token are not in the file.

## Integrity

Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. Porcelain count `257`. Tracked diff remains the same 33 pre-existing names. Phase 2 manifest `c1033f885bb956ff0bbcb461291a967d3b0178d46851f37651fc1564e691b441`. Phase 3 manifest `ca0e9707a84646458be24b232a575e3870e8f2de3c6f5746bdb7388cad2fb100`.

- `forex_bot/oanda_client.py` `02c917ff7cf8a2b58942a8f2945182c3d2ab55959379973978427c875f464b7a`
- `forex_bot/oanda_account_adapter.py` `191466d11e1fac41ef1ccd5603046a3df5c4682f761fde651adcf9229bdf83b5`
- `main.py` `4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb`

File hashes for this directory are in `07_integrity_manifest.json`. The manifest hash is reported with the final verification and is not copied back into this file.

## Remaining gaps

GBP pip value, stake-to-unit mapping, financing, instrument pip location, home conversions, quote freshness, executable size, and strategy profitability are unresolved. Margin used was not in the synthetic summary. Account type and a reporting timestamp were not returned. No exchange-rate fallback was added.

## Blockers for a real diagnostic session

- Authenticated OANDA access is not authorised.
- There is no real credential reader and no live socket path.
- The host constant is the live environment. Practice is rejected and must not be substituted quietly.
- A real token may have trading authority.
- The production client is a different program and is not proven data-only.
- The 5 s and 15 s targets are not a strict deadline for a blocking network operation.

Production deployment remains **NO-GO**.

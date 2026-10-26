# R56_PHASE5_FINAL_READ_ONLY_CONNECTION_REPORT

Overall: **PASS**

`TARGET_ENVIRONMENT = OANDA_LIVE`

`LIVE_NETWORK_ACCESS = NOT_AUTHORISED`

No OANDA connection was made. The production bot was not started. Real credentials were not read. The live entry point is not executable.

## Architecture

`offline_entry.py --offline` confirms a synthetic screen, accepts an in-memory marker, and asks `session_supervisor.py` to run two child processes. Each child is `isolated_worker.py --offline-worker`. The child seals sockets and DNS, checks the Phase 3 gate, calls `get_account_summary` or `get_pricing`, and returns a Phase 2 diagnostic. The parent writes one sanitised log. Phase 2, 3, and 4 files were not modified.

## Two-GET restriction

The transport methods build the path themselves. `validate_outbound` rejects every other method, host, port, scheme, query, body, redirect, retry, and stream. The supervisor will not start a third child. Pricing starts only after the summary child returns `DIAGNOSTIC_RECORDED`.

## Account-changing requests

POST, PUT, PATCH, DELETE, `/orders`, `/trades`, `/positions`, and the other blocked families fail inside the transport. The session cannot call a generic request function because that function does not exist. Production execution modules are not imported. `open_live_connection` raises `LIVE_NETWORK_NOT_AUTHORISED` before `http.client.HTTPSConnection`.

## Credentials during Phase 5

`prompt_hidden_token`, environment reads, dotenv reads, and live activation raise `REAL_CREDENTIAL_USE_NOT_AUTHORISED`. The child argv and the child job do not carry the marker. Logs that match an account id, the marker, or `Bearer ` are stored as `SENSITIVE_OUTPUT_BLOCKED`.

## Process isolation

A child that sleeps for 30 seconds was killed at a 0.5 second parent deadline. Observed wall time **0.5150 s**, `child_alive` false, pricing not sent. A pricing child that slept for 10 seconds was killed with the summary diagnostic kept. Observed session wall **0.6537 s**, status `SESSION_INCOMPLETE`. A cooperative scripted session finished in **0.2766 s**. Killing a process does not cancel a GET that a server has already accepted. No such GET was sent. The local TLS check is not a live handshake.

## Tests

**13 passed, 0 failed, 0 skipped, 3.94 s.**

## Example sanitised output

Session `r56-48e194c2de644e0599b05572ece9599e`, schema `r56.phase5.1`, `SYNTHETIC_TEST_ONLY`, `OANDA_LIVE`, `NOT_AUTHORISED`, `SESSION_COMPLETE_SYNTHETIC`.

The fixture summary shows GBP, balance `100.00`, NAV `100.00`, margin available `100.00`, and margin used `0.00`. `home_currency_source` is `BROKER_REPORTED` because the synthetic field was present. `account_identity_verified` is false and `broker_evidence_complete` is false. EUR_USD bid `1.10000`, ask `1.10020`, spread `0.00020`, quote time `2026-10-21T16:00:00Z`, tradeable true. `executable_order` is `NOT_PRODUCED`. The account identifier is not in the file.

## Integrity

Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. The Phase 2, 3, and 4 manifests and the production client hashes are unchanged. Created-file hashes are in `07_integrity_manifest.json`. The manifest hash is reported with the final verification.

## Remaining limits

GBP pip value, stake-to-unit mapping, financing, pip location, home conversion, quote freshness, executable size, and strategy profitability are unresolved. No `1.35` fallback was added. A real token could still have trading permission. The 5 second and 15 second figures are parent deadlines, demonstrated here with a 0.5 second test deadline.

## Before any real session

A separate written authorisation must name the live host and exactly these two GETs, require the operator screen before any credential prompt, keep the production bot stopped, and keep raw responses out of the log. That session is not authorised by this report.

Production deployment remains **NO-GO**.

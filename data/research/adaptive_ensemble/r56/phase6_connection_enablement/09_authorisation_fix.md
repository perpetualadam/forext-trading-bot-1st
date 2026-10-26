# R56_FINAL_AUTHORISATION_FIX_REPORT

Overall: **PASS**

`REAL_SESSION_SOURCE_ENABLEMENT` remains `False`. No OANDA connection was opened. No real credential was read. The production bot was not started.

## Files changed

- `live_session_gate.py`
- `diagnostic_worker.py`
- `diagnostic_supervisor.py`
- `credential_ipc.py`
- `restricted_live_transport.py`
- `test_phase6_offline.py`
- `01_architecture.md`
- `02_request_and_credential_security.md`
- `03_timeout_and_ipc_evidence.md`
- `04_test_results.md`
- `05_future_one_session_procedure.md`
- `06_integrity_manifest.json` (regenerated after this report)
- `09_authorisation_fix.md` (this file)

`offline_entry.py` was not modified. No new Python module was added. Phases 2–5 and production sources were not modified.

## Worker self-authorisation

`diagnostic_worker.py` no longer calls `confirm_one_session` or `issue_runtime_authorisation`, and it no longer contains the confirmation phrase. A missing capability returns `GRANT_REJECTED` before a fake connection is opened. A parent `CAP_NO` returns `CAPABILITY_REJECTED` before `HarnessConnection.perform`. The real branch, which is reached only after `assert_real_session`, calls `note_parent_ack`. That function checks the source switch before it can create an object, so it raises `REAL_OANDA_SESSION_NOT_AUTHORISED` while the switch is false. A harness grant fails `assert_parent_capability` with `GRANT_REJECTED`. An account id, an API token, and `authorised=true` are not accepted as confirmation.

## Operator confirmation

`run_real_session` renders the OANDA Live host and the two GET paths. `confirm_one_session` accepts only `CONFIRM ONE DIAGNOSTIC SESSION` after that screen is shown. It returns a random receipt id. `accept_confirmation` spends the receipt. A blank answer, a wrong phrase, an unknown id, a second use of the same receipt, and a receipt older than 60 seconds are refused before the credential source is called. With no test seam, the source switch is checked before any of that, and before `input` or `getpass`.

## One-time capabilities

`CapabilityIssuer` keeps a random HMAC key in the parent process. `issue` binds the token to the session id, the step, `api-fxtrade.oanda.com`, port 443, plan `r56.phase6.two-get.1`, and the mode. `REAL_SESSION` mode calls `assert_real_session` first and therefore cannot issue while the switch is false. The token goes only in the stdin frame. The child sends the SHA-256 of the token, not the token. The parent redeems the stored token once and replies `CAP_OK` or `CAP_NO`. A second redeem is `CAPABILITY_REPLAYED`. A different session or step is refused. A negative lifetime is `CAPABILITY_EXPIRED`. `expire_all` runs after the session record is written. The token is included in the output scan and is not written to argv, the environment, or the log.

This is not operating-system isolation and it is not OANDA authentication. Anyone who can write the child stdin can impersonate the parent. The worker can no longer authorise itself from a stored phrase.

## Real-session supervisor

`run_real_session` is separate from `main.py`. Without `transport_seam`, it stops at the source switch. After a future source-gate change, the same function would prompt for the account id and the hidden token and then use the existing child supervisor. The harness seam uses that same supervisor now: confirmation, one capability per step, two children at most, summary before pricing, Phase 2 adapters, the allowlisted log, capability expiry, and child reaping. There is no background loop and no environment or command-line bypass.

## Offline path

`test_real_session_entry_uses_parent_capabilities` calls `run_real_session`, not only `run_authenticated_harness_session`. The seam is the keyword `transport_seam="harness"`. The child is `--authenticated-worker --harness-transport`, which replaces `HTTPSConnection` with a raiser. Responses come from `HarnessConnection`. The test process blocks `socket.socket`. `LiveExchange.real_connections_opened` stayed 0.

## Capability evidence

The issuer tests recorded `CAPABILITY_FORGED`, `CAPABILITY_REPLAYED`, `CAPABILITY_WRONG_SESSION`, `CAPABILITY_WRONG_STEP`, and `CAPABILITY_EXPIRED`. A child launched with no capability returned `GRANT_REJECTED` and no `request_sha256`. A child given a forged token and `CAP_NO` returned `CAPABILITY_REJECTED` and did not open the fake connection. A harness grant did not pass `assert_parent_capability`.

## Two GETs

The successful `run_real_session` recorded two children. The summary path hash matched `/v3/accounts/{accountID}/summary` and the pricing path hash matched the pricing path. Summary status 500 recorded `HTTP_500`, one child, and pricing `NOT_SENT`. A third `SessionBudget.reserve` returned `REQUEST_LIMIT`.

## Timeout and cleanup

The hang case used `request_deadline=0.5`. The record was `CHILD_TERMINATED`, `child_alive` false, one child, pricing `NOT_SENT`, and `SESSION_INCOMPLETE`. Observed wall time was at least 0.5 seconds and below 8 seconds. `LAST_PROC.poll()` was not `None`. The 5 second and 15 second caps remain. A timed-out request is not retried. Capabilities are expired when the record is written.

## Non-disclosure

The account id, the synthetic token, and the capability pattern `[0-9a-f]{64}.[0-9a-f]{64}` were absent from argv, the child environment, `LAST_PUBLIC`, the session logs, and parent stdout. The forged capability was absent from the child ready line, child stdout, and child stderr. The API token is not reproduced in this report.

## Limitations

- The source switch is still false, so a real socket cannot be opened.
- A parent capability is not OANDA authentication and it is not an operating-system sandbox.
- A process that can write the child stdin can send `CAP_OK` after choosing its own token. The production parent sends `CAP_OK` only after a successful redeem.
- `--harness-transport` is an explicit test seam. It cannot open `HTTPSConnection`.
- Killing a child does not cancel a GET a server has already accepted. No such GET was sent.
- GBP pip value, stake-to-unit mapping, pip location, home-currency conversion, financing, executable sizing, and strategy profitability stay unresolved. No `1.35` conversion was introduced.

## Source hashes

- `restricted_live_transport.py` `3df6be9b1422ac52f12a8961cc31b079db4b978b6e0ad27f304d1503f5d545e0`
- `credential_ipc.py` `7ff330c6eff10a929443c817d8a17c80526772f87489b952930c22dde04fccb8`
- `live_session_gate.py` `af6db5c62d934a9ab38076d7114e0e83c1b6e67f7ed0ec1d88e36bad60fc8bc6`
- `diagnostic_worker.py` `59afcac36a67ea210699ce8ea91283f8c9e4cb0f5ceef309f0a40a3525078022`
- `diagnostic_supervisor.py` `769a0ef89d5ecbf8ee531424819e8b7bcab57fc9f1fb10a25cd37066f637adfd`
- `offline_entry.py` `dc00f6b20efd1c02e4c795aae3f794222c58f71582acc55f25dde6797ff54100` (unchanged)
- `test_phase6_offline.py` `6d52900db8bffe62dcee5963b92d97676b8e384585a10b63c1ecbbc802a89692`

## Tests

`python -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r56/phase6_connection_enablement/test_phase6_offline.py`

**14 passed, 0 failed, 0 skipped, 7.08 s.**

## Git integrity

Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. No commit, reset, clean, stash, or checkout was run.

## Confirmations

- Real activation remains disabled.
- No real credential was entered, read, or requested.
- No OANDA Live or Practice connection was made.
- The production bot remained stopped.
- Production deployment remains NO-GO.

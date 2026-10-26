# R.56 final two-issue correction

## 1. Overall result

**PASS**

The two reviewed defects are corrected in the working tree. The Phase 6 offline suite is **22 passed, 0 failed, 0 skipped, 8.40 s**. No mandatory test was skipped.

`REAL_NETWORK_EXECUTION_NOT_TESTED`

These tests do not show that a live OANDA connection would succeed.

## 2. Root cause of each defect

Defect A. In `_execute_authenticated_session`, `tracker.cleanup()` and `issuer.expire_all()` ran after the `except` clauses for `SupervisorRejected` and `KeyboardInterrupt`. An unexpected exception after `Popen` left that function before those calls.

Defect B. `_record` treated `dispatch_mode == "REAL"` as enough to choose `REAL_NETWORK_COMPLETED` and `SESSION_COMPLETE_REAL_DIAGNOSTIC`, while `network_permitted` was written as `False` on every record. A caller-supplied result dictionary could therefore look completed and unauthorised at the same time.

## 3. Code changes

- `diagnostic_supervisor.py`: session body is now `try` / `except` / `finally`. Unexpected exceptions become `SESSION_FAILED` with no stored exception text. Cleanup and capability expiry run after the tracker and issuer exist. `network_permitted`, `network_attempted`, and `broker_response_received` come from parent facts. `_VerifiedRealAuthorisation` can be constructed only after `assert_real_session()`.
- `test_phase6_offline.py`: unexpected-exception coverage on a real harness subprocess, and authorisation-metadata coverage. The old unverified `dispatch_mode="REAL"` record assertion no longer expects a completed live label.
- `02_request_and_credential_security.md`, `03_timeout_and_ipc_evidence.md`, `04_test_results.md`: the cleanup guarantee, the metadata rule, and the new suite count.

`live_session_gate.py` was not changed. The one-session permit design was not changed. `main.py`, `forex_bot/oanda_client.py`, `forex_bot/oanda_account_adapter.py`, production trading modules, strategies, risk management, and Phases 2–5 were not changed.

## 4. Guaranteed cleanup

After `ChildTracker` and `CapabilityIssuer` are created, every exit from the session body reaches `finally`. That block closes parent stdin, stdout, and stderr, kills a child that is still in this tracker, waits for it, and marks every open capability spent. `cleanup()` and `expire_all()` can be called again.

An unexpected exception is stored as `SESSION_FAILED`. `KeyboardInterrupt` remains `SESSION_INTERRUPTED`. A `SupervisorRejected` code is kept. If cleanup itself fails, `child_alive` stays true. `CHILD_CLEANUP_FAILED` is used only when there is no earlier error, so a cleanup failure does not hide `SESSION_FAILED` and a live child is not described as reaped.

Limits. Cleanup covers processes this session added to its tracker. It does not signal unrelated processes. A failure before the tracker exists has no child to reap. Local kill does not cancel a GET a broker has already accepted. No such GET was sent. Exception text, tokens, account ids, capabilities, and Authorization headers are not written into the record.

The five-second request timeout and fifteen-second session deadline are unchanged.

## 5. Unexpected-exception tests

`test_unexpected_exception_reaps_the_child_and_expires_capabilities` drives the existing synthetic worker through `subprocess.Popen` with harness dispatch. The parent socket constructors, including `getaddrinfo`, raise `network_blocked`. The fault points are `after_spawn`, `handshake`, `ipc`, `between_steps`, and `write`.

For each point the returned record has `error_code` `SESSION_FAILED`, `child_alive` false, and `network_permitted` false. `poll()` is not `None`. Parent pipes are closed. Every capability record is spent, and `expire_all()` plus `cleanup()` succeed a second time. The first four faults start one child and leave pricing `NOT_SENT`. The write fault happens after the two harness steps and does not start a third child. Logs do not contain the synthetic token, the account id, `Bearer `, `RuntimeError`, or `Traceback`. Elapsed time stayed under the fifteen-second deadline. `LiveExchange.real_connections_opened` did not increase.

## 6. Real-versus-synthetic metadata rules

`_session_facts` is the parent mapping:

| Condition | network_permitted | network_attempted | broker_response_received |
| --- | --- | --- | --- |
| Synthetic or any unauthorised session | false | false | false |
| Authorised, stopped before a request | true | false | false |
| Authorised, attempted, no response | true | true | false |
| Authorised, response received | true | true | true |

A response is not recorded unless an attempt is recorded. `REAL_NETWORK_COMPLETED` and `SESSION_COMPLETE_REAL_DIAGNOSTIC` require those three facts, error `NONE`, and a reaped child. Authorisation alone produces `REAL_NETWORK_NOT_ATTEMPTED` and an incomplete session. An attempted failure stays `REAL_NETWORK_NOT_COMPLETED`.

`_record` persists `network_permitted: true` only when the dispatch is `REAL`, the parent passed a `_VerifiedRealAuthorisation`, and `REAL_SESSION_SOURCE_ENABLEMENT` is true. Harness dispatch forces the three facts false. Child payloads are not read for these fields. While the gate is false, a persisted record cannot carry `network_permitted: true`. The logical rows above are tested through `_session_facts` and `_outcome_labels` without constructing a live session.

## 7. Authorisation metadata tests

`test_authorisation_metadata_is_consistent_and_not_forgable` checks the four rows above, plus the disabled-gate case through `run_real_session()` and `real_session_entry.launch([])`. Both refuse with `REAL_OANDA_SESSION_NOT_AUTHORISED` before a child or a permit. `_VerifiedRealAuthorisation()` raises the same code.

A forged summary that contains `network_permitted: true` and `BROKER_RESPONSE_RECEIVED`, passed with `session_authorised=True`, still persists `network_permitted` false, `network_attempted` false, `broker_response_received` false, `live_network_access` `NOT_AUTHORISED`, and `SESSION_INCOMPLETE`. A harness record with the same flags stays `SYNTHETIC_TEST_ONLY`. An unattempted pricing payload stays `NOT_SENT`. The sensitive-output scan still matches an account id, a token, a capability, and a bearer header. `real_session_source_enablement` in the record remains false.

## 8. Full offline suite

Command:

`python -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r56/phase6_connection_enablement/test_phase6_offline.py`

**22 passed, 0 failed, 0 skipped, 8.40 s.**

New tests:

- `test_unexpected_exception_reaps_the_child_and_expires_capabilities`
- `test_authorisation_metadata_is_consistent_and_not_forgable`

## 9. Five-blocker controls preserved

`REAL_SESSION_SOURCE_ENABLEMENT` remains `False`. `real_session_entry.py` still refuses before prompts. `prepare_one_session.py` still cannot create a permit while the gate is off. The durable single-use activation record and its atomic consume path are unchanged. Harness and real Authorization checks stay separate. The parent still issues and redeems capabilities. Real dispatch remains `REAL_SESSION`. Harness dispatch remains `HARNESS_SESSION`. The worker still cannot self-authorise. The live host and port, GET-only transport, two endpoints, redirect refusal, retry refusal, the two-request budget, the summary-failure stop, the five-second request timeout, the fifteen-second session deadline, separate log directories, and credential redaction are unchanged.

## 10. Source hashes

SHA-256 of the current files:

- `diagnostic_supervisor.py` `b896026500d1e942bd8095383c2a591e1218dd71d33bdb35e6317b58e0a8383e`
- `test_phase6_offline.py` `f43f3d806a1790cf9884e1f0a9fa548094b0b69b248ba115bb4be4bd6faac217`
- `02_request_and_credential_security.md` `489434a152325c3143cd5bb1686a4c45aad872badb5d00907091889a415590f7`
- `03_timeout_and_ipc_evidence.md` `77b6c0dea7d8db810ab0f2b643567096da22438435bb2e6916e9bdc351dcb532`
- `04_test_results.md` `85b97180c74b8c3c88ea4920ff37c869b202997186be19cfe5aae63dcee111e1`
- `live_session_gate.py` `ae07d4ca969c8696215510a059e7c5c9e6d66933834b3117080e21207bfeee9a`
- `diagnostic_worker.py` `d166928ce498cfeb11c2bbc1f2877afe0ebdf37717298d8782129fcf34e7b70e`
- `restricted_live_transport.py` `ee9e61464e33158475aea467e1ea43c73df174881b83db9934f7f86f47eab91c`
- `credential_ipc.py` `fab8207b6fab2adff13bfc1fb17943e562500d90d7cf3a0d8312f85beac93743`
- `real_session_entry.py` `4c0735b40985b43733776e44c996242c64de34b590aa7e4d8d8f6c808b21b72e`
- `one_session_activation.py` `2dd386c5607bf6e2af6a32ad7adfb40f7bb3af7ff07e471632ab5dd26806b3b5`
- `prepare_one_session.py` `59561926aca5f275ee38dee79206c44c9e8ad02c6f098392c667c95e70e7812d`
- `offline_entry.py` `dc00f6b20efd1c02e4c795aae3f794222c58f71582acc55f25dde6797ff54100`

Production pins, unchanged:

- `main.py` `4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb`
- `forex_bot/oanda_client.py` `02c917ff7cf8a2b58942a8f2945182c3d2ab55959379973978427c875f464b7a`
- `forex_bot/oanda_account_adapter.py` `191466d11e1fac41ef1ccd5603046a3df5c4682f761fde651adcf9229bdf83b5`

Phase manifests, unchanged:

- phase 2 `c1033f885bb956ff0bbcb461291a967d3b0178d46851f37651fc1564e691b441`
- phase 3 `ca0e9707a84646458be24b232a575e3870e8f2de3c6f5746bdb7388cad2fb100`
- phase 4 `6183c33dbec1b334adefa7c2ab663784832cdba806a9a8e99605f26695580b22`
- phase 5 `27026f230e1485e74d462000b6d1d4159a939cd1a500390fc329ea82f8db8cf0`

## 11. Git integrity

Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. `git status --porcelain` is 257 lines. The 33 previously dirty tracked names are unchanged. Phase 6 remains untracked. No commit, reset, clean, stash, or checkout was run.

## 12. Source gate

`REAL_SESSION_SOURCE_ENABLEMENT = False` in `live_session_gate.py`. The assignment `REAL_SESSION_SOURCE_ENABLEMENT = True` is not present.

## 13. Activation permit

`phase6_connection_enablement/real_activation` does not exist. No `one_session.permit` was created. Tests that arm a permit use a temporary directory only.

## 14. Credentials

No `.env` file was read. No real token was requested. The offline tests use the existing synthetic account id and synthetic token. Those values are rejected from persisted logs.

## 15. OANDA

No connection to OANDA Live or Practice was opened. Parent DNS lookup is blocked. The exercised child is the harness worker.

## 16. Production bot

`main.py` was not started. The production trading bot was not started. No order was placed, modified, or closed.

## 17. Unresolved blocker

None for these two defects.

## 18. Standing limit

`REAL_NETWORK_EXECUTION_NOT_TESTED`

# R.56 record-persistence failure fix

## 1. Overall result

**PASS**

An unexpected failure while creating or writing a session record is no longer returned as a completed diagnostic session. The Phase 6 offline suite is **23 passed, 0 failed, 0 skipped, 8.51 s**.

`REAL_NETWORK_EXECUTION_NOT_TESTED`

These tests do not show that a live OANDA connection would succeed.

## 2. Confirmed root cause

In `_execute_authenticated_session`, record creation and `write_text` sat in one `try`. The matching `except` built a fallback record with `record_error`. That value was changed to `SESSION_FAILED` only when `fault_at == "write"`. Any other exception, including a disk error after a clean session, left `record_error` as `"NONE"`.

`_record` treats error `"NONE"` on the harness path as `SESSION_COMPLETE_SYNTHETIC`. The fallback then attempted a second write. A successful session could therefore be reported, and a second log file could be created, after the original write had failed. The `fault_at="write"` regression did not catch this because it changed `record_error` before raising.

## 3. Exact source change

`diagnostic_supervisor.py` only:

- `_persist_record` is the single writer.
- `_mark_persistence_failed` sets `error_code` to the sanitised failure, `session_status` to `SESSION_INCOMPLETE`, and `record_persisted` to false. If the label was `REAL_NETWORK_COMPLETED`, it becomes `REAL_NETWORK_NOT_COMPLETED`. Summary and pricing rows, and the authorisation, attempt, and response flags, are left as they were.
- An unexpected exception in the authenticated record path uses `RECORD_PERSISTENCE_FAILED`. The explicit `fault_at="write"` injection still uses `SESSION_FAILED`, so that older regression stays separate.
- The failed attempt does not call the writer again. An empty file created by `_allocate` before the write is removed. A non-empty file is not rewritten.
- If a fallback record cannot be built, the function raises `SupervisorRejected` with the sanitised code and no exception text.
- `run_offline` uses the same writer. A write failure there is also `RECORD_PERSISTENCE_FAILED` with `record_persisted` false, and it is not written again.
- `record_persisted` is a new allowlisted field. It is true only in the text passed to a write that then succeeds.

`live_session_gate.py`, `one_session_activation.py`, `real_session_entry.py`, `prepare_one_session.py`, `restricted_live_transport.py`, and `diagnostic_worker.py` were not modified. The `try` / `finally` child cleanup is unchanged.

## 4. Unexpected persistence-failure test

`test_unexpected_persistence_failure_is_not_a_successful_session` replaces `_persist_record` with a function that raises `OSError("synthetic disk failure")`. The session is the real harness subprocess path in `_execute_authenticated_session`, not `fault_at="write"`.

The returned record has `error_code` `RECORD_PERSISTENCE_FAILED`, `session_status` `SESSION_INCOMPLETE`, and `record_persisted` false. It does not contain `SESSION_COMPLETE_SYNTHETIC`, `SESSION_COMPLETE_REAL_DIAGNOSTIC`, `REAL_NETWORK_COMPLETED`, `OSError`, or `synthetic disk failure`. No log file contains a completed session, `error_code` `"NONE"`, `record_persisted` true, or the exception text.

`test_unexpected_exception_reaps_the_child_and_expires_capabilities` still injects `fault_at="write"` and still expects `SESSION_FAILED`.

## 5. Response received before the write failed

The same test lets both harness requests finish. The in-memory record still has the summary and pricing results, home currency `GBP`, and `EUR_USD` in the pricing diagnostics. `children_started` is 2. `network_permitted`, `network_attempted`, and `broker_response_received` stay false, which is the harness authorisation state. The session status is the persistence failure, not a completed network session.

## 6. Error and completion labels

`error_code` is not `"NONE"`. `session_status` is `SESSION_INCOMPLETE`. `raw_response_persisted` stays false. `record_persisted` stays false because the writer raised. `live_network_access` stays `NOT_AUTHORISED` on this harness session. A `REAL_NETWORK_COMPLETED` label is removed if a persistence failure happens after that label was selected.

## 7. Child cleanup and capability expiry

The existing `finally` block still runs before the record write. The test observed `poll()` was not `None`, parent pipes were closed, and every capability record was spent. `cleanup()` and `expire_all()` succeeded again. Two children were started and no third request was added.

## 8. Sensitive-output sanitisation

The returned record and the log directory do not contain the synthetic token, the account id, `Bearer `, `OSError`, or `synthetic disk failure`. The failure code is `RECORD_PERSISTENCE_FAILED`.

## 9. Complete offline suite

Command:

`python -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r56/phase6_connection_enablement/test_phase6_offline.py`

**23 passed, 0 failed, 0 skipped, 8.51 s.**

## 10. Source hashes

SHA-256:

- `diagnostic_supervisor.py` `f27b77277de7e2be7be4158430a22bd4dae0585819c98a81500f418dc5f54933`
- `test_phase6_offline.py` `2f59da90740c3b0d69dbca8ec6526d6ee7efc80735f5b05efb9fee0311dfb0b4`
- `03_timeout_and_ipc_evidence.md` `527aa6aa3a4d6161916ab093ffa898e90892b136793e87bee4a0443df8972c1f`
- `04_test_results.md` `2e715793125388a0e6a4b13a7bc9fcc37d980a8871297c93bd4c8c1ff2668461`
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

`REAL_SESSION_SOURCE_ENABLEMENT = False`. The assignment `REAL_SESSION_SOURCE_ENABLEMENT = True` is not present.

## 13. Activation permit

`phase6_connection_enablement/real_activation` does not exist. No permit was created.

## 14. Credentials

No `.env` file was read. No real token was requested. The new test uses the existing synthetic account id and synthetic token.

## 15. OANDA

No connection to OANDA Live or Practice was opened. Parent DNS lookup remains blocked. The child was the harness worker.

## 16. Production bot

`main.py` was not started. The production trading bot was not started. No order was placed, modified, or closed.

## 17. Standing limit

`REAL_NETWORK_EXECUTION_NOT_TESTED`

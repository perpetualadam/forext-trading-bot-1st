# Phase 6 test results

Command:

`python -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r56/phase6_connection_enablement/test_phase6_offline.py -q`

Result after the record-persistence correction: **23 passed, 0 failed, 0 skipped, 8.51 s**. `REAL_NETWORK_EXECUTION_NOT_TESTED`. The added test is `test_unexpected_persistence_failure_is_not_a_successful_session`.

Result after the two-issue correction: **22 passed, 0 failed, 0 skipped, 8.40 s**. `REAL_NETWORK_EXECUTION_NOT_TESTED`. The added tests are `test_unexpected_exception_reaps_the_child_and_expires_capabilities` and `test_authorisation_metadata_is_consistent_and_not_forgable`.

Result after the five-blocker readiness correction: **20 passed, 0 failed, 0 skipped, 7.89 s**. `REAL_NETWORK_EXECUTION_NOT_TESTED`. The source gate stayed false. No real activation permit was created. `test_real_session_entry_uses_parent_capabilities` records `REAL_DISPATCH_CONTRACT_VERIFIED` for the real command and IPC, `SHARED_SUBPROCESS_FLOW_VERIFIED` for the harness child processes, and `REAL_NETWORK_EXECUTION_NOT_TESTED` for the real worker.

The original seven tests still cover live mode off, real credential and prompt rejection, blocked sockets, fixed host, GET-only methods, the two endpoints, offline selector substitution, the six-pair query, no third child, no redirect, retry, proxy, or cookie, TLS flags, oversized and invalid JSON, HTTP 401, 403, 429, and 5xx, summary failure stopping pricing, secret-free argv and logs, IPC close, child kill and reap, no production imports, and unchanged Phase 2–5 and `main.py` hashes.

The four added tests cover the correction: offline seal without sealing the authenticated harness, `LiveExchange` selected only around an injected harness, the supplied account id used in the path, valid and invalid account ids, IPC rejection of malformed, oversized, second, nested, and real-session frames, exact redaction of an account id that does not match the old pattern, the two exact GET targets, method and account-changing rejection, redirects and retries, TLS verification, summary failure blocking pricing, and `HTTPSConnection` not opened.

No packet was sent to OANDA. The TLS assertion reads a local `SSLContext` only. The harness connection is not a socket.

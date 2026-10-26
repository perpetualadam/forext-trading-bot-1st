# Phase 6 architecture

`TARGET_ENVIRONMENT = OANDA_LIVE`

`LIVE_NETWORK_ACCESS = NOT_AUTHORISED`

`REAL_SESSION_SOURCE_ENABLEMENT = False`

The runnable entry is `offline_entry.py --offline`. It reuses the Phase 5 confirmation screen and synthetic credential object, then `diagnostic_supervisor.py` starts one child per GET. The child is `diagnostic_worker.py --offline-worker`. Offline mode seals sockets before the job and selects `FakeExchange`. `run_real_session` is the real dispatch. While the source switch is false it returns `REAL_OANDA_SESSION_NOT_AUTHORISED` before any prompt. After a future source-gate change it launches `--authenticated-worker` with `REAL_SESSION` IPC and a `REAL_SESSION` capability. It does not call the harness session. `run_authenticated_harness_session` stays on `--authenticated-worker --harness-transport` and `AUTHENTICATED_HARNESS` frames. A mixture of those modes is `MODE_MISMATCH`. The worker does not confirm the session and does not mint a network grant.

The standalone operator command is `real_session_entry.py` with no arguments. It calls `run_real_session`. While the source switch is off it exits 2 before a prompt or a child. A future session also consumes a one-use permit before credentials. Normal execution does not create that permit. Real diagnostic records, when a future session is separately authorised, go under `real_diagnostic_logs`, not `synthetic_logs`.

The future authenticated path is selected only by `select_exchange("AUTHENTICATED_HARNESS", connection=...)`. That returns `LiveExchange` wrapped around a `HarnessConnection` injected by the test. The harness is not a socket and is not accepted from argv or the environment. Both modes use `validate_outbound`, the Phase 2 diagnostic adapters, the 1,048,576-byte limit, and exact-value output protection.

`LiveExchange.exchange` still contains the `http.client.HTTPSConnection` call. With no injected harness it calls `assert_real_session()` and then `assert_runtime_authorisation` with the grant object the caller supplied. While the source switch is false the first check raises `REAL_OANDA_SESSION_NOT_AUTHORISED` before `HTTPSConnection`. `issue_runtime_authorisation()` raises the same code and never returns a grant. A synthetic confirmation does not change either gate. There is no environment or command-line bypass. The application allowlist is not an operating-system network sandbox.

Phase 3 still checks the offline synthetic plan. It rejects any account id other than its pinned synthetic id, so the authenticated harness does not send a non-synthetic id through that gate. Phase 6 builds and checks that path itself.

A socket monkeypatch is not treated as a network sandbox. Offline mode seals the child. The authenticated harness does not. The restriction that remains is the transport allowlist. A child that ignored the transport could still open a socket once the seal is absent. Process kill does not cancel a GET a server has already accepted. No such GET is sent while the gates stay closed.

A future edit that sets `REAL_SESSION_SOURCE_ENABLEMENT` to true is a separate authorisation. This phase does not make that edit, and that edit alone still does not pass the runtime grant.

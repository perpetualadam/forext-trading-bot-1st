# Timeout and IPC evidence

The parent uses `communicate(timeout=min(request_deadline, session_remaining))`. That is the wall clock. The child sleep does not watch it. After `TimeoutExpired` the parent calls `kill()` and waits until the process is reaped. A socket timeout is not this control, and none was exercised.

The correction did not change that parent path. The offline suite still asserts:

| Case | Child | Deadline | Assertion that passed |
| --- | --- | --- | --- |
| Hang on summary | `sleep(30)` | 0.5 s request, 15 s cap | `CHILD_TERMINATED`, one child, pricing `NOT_SENT`, `child_alive` false, wall at least 0.5 s and under 8 s, IPC write end closed |
| Ignore on pricing | summary completes, pricing `sleep(10)` | 0.5 s | `CHILD_TERMINATED`, summary `DIAGNOSTIC_RECORDED`, session incomplete, wall under 8 s |
| Third child | `SessionBudget` | two reserves | the third reserve is `REQUEST_LIMIT` |
| Summary failure | HTTP error or transport rejection | normal | pricing is not started |

The in-process harness still does not start a child and does not seal the network. `run_authenticated_pair` returns no pricing result when the summary error is not `NONE`. `run_authenticated_harness_session` starts `--authenticated-worker --harness-transport` twice. `run_real_session` does not. Its dispatch contract names `--authenticated-worker` without the harness flag, IPC mode `REAL_SESSION`, and capability mode `REAL_SESSION`. That real worker was not launched. The parent redeems one capability before each request and expires every capability when the session record is written. A summary HTTP 500 stops before the pricing child. A summary child that sleeps for 30 seconds is killed at a 0.5 second deadline, reaped, and does not start pricing. Bare `--authenticated-worker` returns code 2 without reading the stdin token.

The reaped offline process was not still running. Killing the child does not cancel a GET a server has already accepted. No GET was sent.

`KeyboardInterrupt` and any other unexpected exception are caught around the authenticated session. `ChildTracker.cleanup` and `expire_all` run in a `finally` block after the tracker and issuer exist, so a failure after the child is spawned still closes the parent pipes, kills any child that is still running, and waits until it is reaped. The same cleanup is safe to call again. A cleanup error does not replace an earlier session error, and it does not claim the child was reaped. Outstanding capabilities are marked spent. An interrupt does not start pricing and does not retry. A failure while building or writing the session record becomes `RECORD_PERSISTENCE_FAILED`. That result is not a completed session, `record_persisted` stays false, and the failed write is not tried again. Request rows already collected stay in the in-memory record. An empty file created before the failed write is removed. On Windows, press Ctrl+C in that diagnostic console, then if a `diagnostic_worker.py` process from this directory is still listed, stop only that process id. Do not stop every Python process, and do not start or stop `main.py`. Local termination does not undo a GET OANDA has already accepted. The local TLS context check is not a live handshake, and these tests do not show that OANDA is reachable.

# R.56 Phase 5 architecture

`TARGET_ENVIRONMENT = OANDA_LIVE`

`LIVE_NETWORK_ACCESS = NOT_AUTHORISED`

The collector is a separate program under `phase5_connection/`. It does not import the production bot, the production OANDA client, or an execution module.

## Process split

1. `operator_confirmation.py` shows the two-GET plan. A synthetic phrase sets `network_permitted` to false.
2. `credential_gate.py` accepts only an in-memory synthetic marker. Real entry points raise `REAL_CREDENTIAL_USE_NOT_AUTHORISED`.
3. `session_supervisor.py` starts one child per request. The parent alone owns the wall-clock deadline.
4. `isolated_worker.py` seals sockets, DNS, and HTTP connection classes, then runs one step.
5. `restricted_https_transport.py` exposes `get_account_summary` and `get_pricing`. The live `http.client` call sits behind `perform_live_exchange()`, which raises before a connection is constructed.
6. The child loads the Phase 3 gate and the Phase 2 adapters by file path, reduces the scripted document, and writes JSON to stdout.
7. The parent checks that stdout is sanitised and writes one log under `synthetic_logs/`.

A synthetic confirmation does not authorise a real session. `--live`, `--connect`, and `--authenticate` return exit code 2.

## Deadlines

| Control | Where it is enforced | Cap |
| --- | --- | --- |
| Per-operation | Scripted connector. It does not block on a socket. | Not a network timeout |
| Per-request | Parent `communicate(timeout=...)` | 5 seconds |
| Session wall clock | Parent clock from the first spawn. A later child is not started at zero remaining time. | 15 seconds |
| Child termination | `process.kill()` after the timeout, then a second wait to reap the process | The request deadline that was actually set |

The offline tests use a 0.5 second request deadline so the suite does not wait 5 or 15 seconds. The same parent timeout path enforces both. A deadline above 5 or 15 seconds is rejected.

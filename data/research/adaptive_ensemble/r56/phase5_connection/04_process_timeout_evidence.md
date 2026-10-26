# R.56 Phase 5 process and timeout evidence

`LIVE_NETWORK_ACCESS = NOT_AUTHORISED`

The child seals `socket.socket`, `create_connection`, `getaddrinfo`, `ssl.SSLSocket`, `wrap_socket`, and the `http.client` connection classes after those modules have been imported. A scripted DNS call in the child returns `NETWORK_SEALED`.

The parent does not send the synthetic marker on the command line. The child argv is the interpreter, `-B`, `isolated_worker.py`, and `--offline-worker`.

## Measured termination

The child sleep does not watch the deadline. The parent `communicate` timeout does. After `TimeoutExpired`, the parent calls `kill()` and waits for the process to exit. These runs did not wait 30 seconds or 10 seconds.

| Case | Child behaviour | Parent deadline | Observed wall | Result |
| --- | --- | --- | --- | --- |
| Hang on summary | `sleep(30)` and no further requests | 0.5 s request, 15 s session cap | 0.5150 s | `CHILD_TERMINATED`, one child, pricing `NOT_SENT`, `child_alive` false |
| Ignore on pricing | Summary finishes, then pricing `sleep(10)` | 0.5 s for the pricing child | 0.6537 s for the whole session | `CHILD_TERMINATED`, two children, summary diagnostic kept, session incomplete |
| Happy synthetic session | Both children return immediately | 5 s request cap, 15 s session cap | 0.2766 s | `SESSION_COMPLETE_SYNTHETIC`, termination `NOT_REQUIRED` |

The reaped hang and ignore processes were not still running. A killed pricing child left return code 1. No success status was written for either terminated session. An earlier complete log was left unchanged.

Killing the child does not cancel a request that a remote server has already accepted. This collector's remote operations are GET-only, and no remote request was made. `live_socket_timeout` was not exercised. The local TLS context requires `CERT_REQUIRED` and hostname checks; that check is not a live handshake.

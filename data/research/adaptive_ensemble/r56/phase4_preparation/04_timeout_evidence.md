# R.56 Phase 4 timeout evidence

`timeout_enforcement = PHASE_BUDGET_ENFORCED_ON_OFFLINE_INTERFACE`

`live_socket_timeout = NOT_EXERCISED`

`dns_getaddrinfo` was not called. The test process replaces `socket.socket`, `socket.create_connection`, and `socket.getaddrinfo` before the candidate is loaded. Each blocked call raises `network_blocked`.

The 5.0 second and 15.0 second figures are budgets on the offline phase interface. They are not a wall-clock guarantee for DNS, TLS, or a socket. Process isolation was not added. A blocking operation that ignores the budget is detected after it returns, and the session then stops.

## Cooperative stalls on an injected clock

No wall-clock wait was used for these rows. The double advances the injected clock by the remaining phase budget plus `0.0001` when a stall is larger than that budget, then `require_time()` raises.

| Case | Requested budget | Stall presented | Observed injected clock | Code | Later phase |
| --- | --- | --- | --- | --- | --- |
| Stalled connect | 5.0 s | 30 s | 5.0001 | `REQUEST_DEADLINE` | TLS not run |
| Stalled TLS | 5.0 s | 30 s | 5.0001 | `REQUEST_DEADLINE` | Write not run |
| Stalled headers | 5.0 s | 30 s | 5.0001 | `REQUEST_DEADLINE` | Body not read |
| Stalled body read | 5.0 s | 30 s | 5.0001 | `REQUEST_DEADLINE` | Body not parsed |
| Session gap after summary | 15.0 s session | injected advance 15.0 | 15.0000 | `SESSION_DEADLINE` | Pricing phases not run |

The session-gap row did not wait 15 seconds. After a successful synthetic summary, the double advanced the injected clock by 15.0. Pricing then failed `SESSION_DEADLINE` with `pricing_request.result = REJECTED` and `session_status = SESSION_INCOMPLETE`. Connect had run once.

## Slow body

A 500-byte body in 10-byte chunks, with `0.05` s charged per chunk and a `0.30` s request budget, stopped at injected clock `0.3001`. The last chunk's delay exceeded the remaining budget, so the clock moved by the remainder plus `0.0001`. Chunks served were inside 1 to 10. The partial body was not treated as success.

## Blocking sleep that ignores the budget

Measured in the offline suite and repeated once after it:

| Item | Value |
| --- | --- |
| Request budget | 0.05 s |
| Sleep | 0.20 s on `connect`, `ignore_timeout=True` |
| Clock | `time.monotonic` |
| Result | `REQUEST_DEADLINE` |
| Wall elapsed around the call | 0.2182 s |
| `observed_wall_seconds` | 0.2005 |
| `observed_clock_seconds` | 0.2162 |
| Phases run | `connect` only |

The sleep finished. TLS did not run. Pricing was `NOT_SENT`. The 0.05 s budget did not preempt the sleep. That limitation is unresolved for a real DNS lookup, TLS handshake, or socket read.

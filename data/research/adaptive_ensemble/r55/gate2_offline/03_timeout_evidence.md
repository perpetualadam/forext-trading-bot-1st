# Timeout evidence

The approved caps are 5.0 seconds per request and 15.0 seconds for the session. `SessionClock` rejects a larger value. Tests may use a shorter budget on the same clock. The clock uses `time.monotonic` unless a test injects a time function.

Each phase receives `min(per-request remaining, session remaining)`. The transport checks that budget before the phase and again between body chunks. A slow trickle therefore stops on accumulated wall-clock time even when every individual read returns inside its own timeout. That is the opposite of a socket inactivity timer, which would keep going while bytes continued to arrive.

The live socket path was not exercised. The tests blocked `getaddrinfo`, `socket.socket`, and `create_connection`. These measurements show the offline interface, not an operating-system DNS or TLS syscall.

## Observed runs

Attempt 2, 22 Oct 2026. `stopped` means the session classified the overrun and did not continue. `second_prevented` means pricing did not start, except for the row that stalls pricing after instruments already succeeded. `stale_removed` means a pre-written success file was gone.

| Case | Expected seconds | Observed seconds | Stopped | Second prevented | Stale removed |
| --- | --- | --- | --- | --- | --- |
| Stalled resolve | 0.2500 | 0.2501 | yes | yes | yes |
| Stalled connect | 0.2500 | 0.2504 | yes | yes | yes |
| Stalled TLS handshake | 0.2500 | 0.2502 | yes | yes | yes |
| Stalled response headers | 0.2500 | 0.2504 | yes | yes | yes |
| Slow body, 50 chunks available | 0.3000 | 0.3003 | yes | yes | yes |
| Several pauses against a 0.30 session budget | 0.3000 | 0.3001 | yes | yes | yes |
| Timeout after a successful instruments response | 0.2500 | 0.2502 | yes | pricing handshake did not run | yes |
| Configured 5.0 second cap, 30 second stall | 5.0000 | 5.0001 | yes | yes | yes |
| Injected clock reaching the 15.0 constant | 15.0000 | 15.0000 on the injected clock | yes | yes | yes |
| Non-cooperative connect that ignored its 0.05 second timeout | 0.0500 | 0.2505 | session stopped | yes | yes |

The slow-body test required the reader to stop after 1 to 10 of the 50 prepared chunks. It passed. The configured five-second test passed a timeout of at most 5.0 seconds into connect and returned in 5.0001 seconds.

The 15.0 second row did not wait 15 wall-clock seconds. After instruments completed, the injected clock jumped from 0 to 15.0 and the controller refused to start pricing. The same `SessionClock` class, using `time.monotonic`, stopped a real pause sequence at 0.3001 seconds when the session budget was 0.30 seconds.

## What is not enforced

A double that sleeps for 0.25 seconds and ignores a 0.05 second timeout is not preempted. The session detects the overrun afterwards, skips the next phase, and writes no success file. Observed time was 0.2505 seconds. Process isolation was not added.

`socket.getaddrinfo` cannot be bounded by this timeout argument, and this stage does not call it. A future authenticated session would need a separately approved DNS deadline before any live lookup. Until that exists, the five-second and 15-second caps are enforced for the offline phase interface and are not a guarantee for blocking DNS, an ignored timeout, or a real TLS socket.

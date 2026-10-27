# Request guard and deadline

`oneshot.py` fixes a canonical specification SHA-256; mutating the exported
display dictionary cannot change the accepted request. Method, live host,
EUR_USD path and all six literal parameters must match. Caller headers, proxies,
other instruments, account/write endpoints and alternate hosts refuse.
`oneshot_transport.py` reuses V2.6 `CandleTransport` with **attempts=1** and
injected responses only. HTTP 503/429, redirect and connection-failure tests
verify one sender call; no retry, pagination or polling is available.

## Synthetic request budget

Normal code can initialise only NOT_AUTHORISED. Only tests seed synthetic
AUTHORISED_NOT_CONSUMED journals and separate identity/spec-bound grants, inside
explicit fixture namespaces. No real-grant schema or credential-loading path is
implemented. The runtime never authorises itself.

An OS byte-range lock on Windows / flock on POSIX covers reservation through
completion. Under that lock, an unused grant is atomically moved to immutable
claimed evidence, flushed, then REQUEST_RESERVED is atomically published and
hash-checked. Only after the RESERVED handshake does the parent release an
in-memory synthetic secret through an anonymous pipe. REQUEST_ATTEMPTED is
durable before dispatch. RESPONSE_RECEIVED precedes validation/publication;
SESSION_CONSUMED is published last. Runtime transitions cannot authorise/reset.

Claimed grants, consumed journals, missing/corrupt journals, stale .pending files,
duplicate completion files and ambiguous hardlinks refuse reuse. Crashing before
the reservation journal but after claiming the grant burns the session without
dispatch. Before any claim/secret release, preparation failure may leave unused
synthetic permission; the controller still never retries automatically.

Known HTTP/validation refusal may leave REQUEST_ATTEMPTED or RESPONSE_RECEIVED;
these are consumed, not unused permission. REFUSED describes processing refusal,
not proof that no dispatch happened. Abrupt worker death/timeouts return
OUTCOME_UNKNOWN without resetting state. Hardware power-loss/firmware guarantees
and malicious archive-owner rollback are outside the tested process-crash model.

## Deadline and process fence

Monotonic timing starts on entry; accepted total budgets are 0.5–15 s. Up to
1 s (one third for smaller budgets) is withheld for cleanup. Preparation,
reservation, fixture connection/headers/body, validation, publication and final
persistence run in a disposable `python -I -S -B` worker. Windows uses a
kill-on-close Job Object before startup/secret release; POSIX uses a new process
group. The parent fences even a successful worker and verifies process exit.
No worker can create subprocesses or sockets under its audit hook.

Synthetic stalls exercise every listed phase, including after a pending file is
flushed but before rename. Tested 1.5 s calls include cleanup. There is no claim
of universal hard real-time bounds for process creation/OS stalls; actual TLS
blocking remains unverified. A local kill cannot prove remote non-receipt,
remote cancellation or exactly-once delivery. Fencing uncertainty/overrun must
block future authorisation, never trigger retry.

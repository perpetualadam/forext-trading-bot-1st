# Previous outcome and timeout correction

Read-only inspection on 2026-10-28 found a claimed LIVE grant for request `36c7d101ab3f4fe3ae3889408735bdc7`, journal `REQUEST_ATTEMPTED` / attempts=1, and worker claim PID 7984 (parent 23508). Neither process was still present. No response batch or pending publication was present. The grant was created and consumed; it must never be reused. The original code records REQUEST_ATTEMPTED before asking for the token, so that state does not establish HTTP dispatch. With no durable dispatch receipt, HTTP outcome remains UNKNOWN. No retry is authorised.

Preserved file SHA-256 values:

- journal.json: `e81d6cb96b76a114ef6046ff28abca425af4416c2f8f2e6e3ea81ec31ea2fdc9`
- grant.claimed.json: `b4a524d24f1b5e8735cc26c8adfecd37575d0bfe4f63ecf6d491292993b5e6d4`
- worker.claimed.json: `d605487ce65931b9ddb80b033fa1763e6485199650182b6c841e6226746c950c`

The old controller started its 15-second budget before reservation/startup and passed the remaining time to hidden input. A timeout could therefore produce OUTCOME_UNKNOWN before token delivery. The evidence cannot prove that this was the only cause of the reported result.

Local implementation now separates three bounded phases: up to 15 seconds from final confirmation for grant/reservation/startup, up to 120 seconds from the durable worker claim for hidden token input, then 15 seconds from entry to begin_acquisition immediately after token validation. The acquisition budget includes phase validation/publication, IPC handoff, network, candle validation, persistence and fencing; its last second is reserved for cleanup. A version-2 grant has a maximum 150-second lifecycle, not a 150-second network budget. Network remaining() still rejects budgets over 15 seconds. No hard real-time guarantee is made for OS scheduling or uninterruptible kernel I/O.

The worker consumes the existing durable attempt before input. A new immutable acquisition.json binds the post-input start/deadline to the session, source and parent/worker IDs. Network permission requires this marker and an unexpired acquisition phase. Missing, pending or malformed phase state fails closed. Expired startup cannot claim an unused grant. Crashes/timeouts never reset state or authorise retry.

Rights, endpoint and exact source/request confirmation requirements, terminal-only hidden credentials, exact GET, one attempt, zero retries, no redirects/pagination/fallback and protected storage remain intact. No credential values were read during this task. No OANDA request was made. Operational trading code and R.56 gates/markers remain unchanged; scheduler and local data are preserved. Production trading remains NO-GO.

Only the isolated hidden-input helper, its integration behind the published unconditional admission refusal, tests and reports are eligible for publication. The real version-2 authority, controller and worker changes remain local and require separate publication approval. The published controller is not activated or migrated by the usability commit.

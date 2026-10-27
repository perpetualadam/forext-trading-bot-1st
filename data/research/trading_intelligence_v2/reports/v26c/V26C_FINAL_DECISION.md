# V2.6C decision — 2026-10-27

`TIV26C_SINGLE_REQUEST_PREPARATION_PARTIALLY_VERIFIED`

Baseline: branch `main`, HEAD `0157e18369b700043c357b10c1565c9b69378554`.
Three pre-existing modified scheduler files and unrelated untracked work were
preserved. Scheduler contents were not inspected or emitted; the Git internal
read caveat below prevents certifying a strict no-content-read boundary.
No operational source changed.

Delivered: explicit native archive binding; existing V2.6 candle validator and
transport adapters; synthetic single-use grant/journal lifecycle; disposable
process supervisor; executable crash, concurrency, persistence and deadline
tests; non-executable first-request specification. The existing multi-batch
downloader and its retry policy remain unchanged and are not a one-shot entry point.

The new controller deliberately understands **synthetic grants only**. There is
no authenticated command, credential loader or real-grant authorisation writer.
An operator-created approval-shaped file cannot activate its fixture worker.
This is tested preparation, not an enabled authenticated downloader.

## Required answers

- **At most one authenticated attempt across crashes/restarts?** Not yet an
  established authenticated integration guarantee. The same-filesystem synthetic
  state machine demonstrates at most one dispatch, including two-process races
  and interrupted persistence. Real execution is unavailable, so zero
  authenticated attempts occurred. A future reviewed live bridge must preserve
  this state machine and use transport `attempts=1` inside the fenced worker.
- **Strict overall deadline without retry?** Process-fenced synthetic blocking
  phases terminate within tested budgets without retry. Default budget is 15 s,
  including a 1 s cleanup allowance. This is not a universal hard real-time
  guarantee: process creation, kernel stalls and OS scheduling are not bounded
  by Python. No actual TLS/socket operation or broker cancellation was tested.
  `FENCING_UNCONFIRMED`/`DEADLINE_OVERRUN` never authorise another attempt.
- **Protected archive only?** Native binding accepts only the approved external
  root, verifies NTFS, ownership, ACLs and pinned directory identities, and holds
  replacement-denying handles. Only explicitly labelled synthetic fixtures may
  use repository ignored outputs. No authenticated archive was created there.
- **Non-account endpoint supported now?** `ENDPOINT_SUPPORT_UNVERIFIED`.
- **Usage permission sufficiently established?**
  `USAGE_PERMISSION_NOT_FULLY_ESTABLISHED`.

Before a live request: establish endpoint and applicable usage evidence; review
the exact interval without assuming ten candles; review a native session/grant
schema and an authenticated in-memory bridge; integrate that bridge into this
worker rather than the multi-batch retry loop; verify its synthetic TLS/network
blocking and failure paths; explicitly approve one scoped live session. No
actual token, private agreement or API-host probe is needed for this review.

Final checks: 71 Windows tests, 71 Ubuntu tests, 39 native synthetic checks and
556 unchanged Windows regressions passed: **737 checks, 0 failures, 0 errors,
0 skips** across the final runs. All 210 pre-existing research/protected source
hashes match. Development failures and their corrections are recorded separately.

Research-only CI coverage is prepared locally. **No commit or push:** the actual
authenticated bridge and actual TLS deadline verification remain missing, so
the policy against committing incomplete implementations holds publication.
HEAD remains the baseline above. No new hosted CI run exists. The prior full
suite remains failed; nothing here establishes overall green CI. Intended new
source/report/workflow changes were reviewed; pre-existing scheduler diffs were
not displayed. An unscoped `git diff --name-only` emitted filenames only, but
Git may have read modified scheduler files internally. Strict no-content-read
compliance cannot therefore be certified; this is an additional publication
blocker. No remote fetch was needed for a push that was not attempted.

No real/practice API request, credential/.env access, production database,
operational gate, permit, trading loop or broker write occurred. Stop at V2.6C.
**Production trading remains NO-GO.**

# R.87C exposure contract proposal

Status: proposed for review; no operational-source implementation authorised by this document.
Production trading remains **NO-GO**. No commit or push is proposed.

## Scope and evidence

Local inspection identified branch `main` at `883752f91510f639d354f090331446dcc6ade0a8`. Existing scheduler-file modifications must remain untouched; their contents are outside this review. Cloud uncommitted repairs have not been transferred. The cloud reference HEAD is `529277b837e15c2bda964e2a258e4c6badc121d3`.

The local discovery function records broker discoveries in `broker_observations`, outside managed `positions`. The USD-direction guard iterates only `positions`. Source-isolated synthetic checks reproduced count zero for a known broker position both with an empty managed book and with overlapping window-paper state. These checks were not the named pytest tests or an end-to-end reconciliation run.

The proposed contract requires **count 1 in both cases**. Preserve the count-one assertions associated with:

- `test_usd_guard_counts_broker_discovery_without_management_authority` (absent from the inspected local checkout).
- `test_restart_window_paper_cannot_hide_live_broker_position` (present locally, with older management-import expectations requiring separate test repair).

No complete green suite result exists. Historical cloud results are not local validation.

## Safety invariants

1. Exposure visibility and management authority are separate capabilities. A discovery may constrain new risk without becoming a managed position.
2. Broker observations remain `observation_only=True`, outside the managed registry. No adoption, displacement of paper, close, resize, SL/TP edit, MFE management, strategy attribution, or recovery authority follows from counting them.
3. Paper, simulated, and window-paper rows contribute zero live broker exposure and cannot hide a broker observation.
4. An uncertain exposure view blocks new broker risk. It must never be converted into a successful zero count.
5. This proposal changes neither strategy/sizing/SL/TP policy nor management permissions, live permits, consumed markers, or trading-gate configuration. Existing management paths remain outside scope; this contract grants no new permission to them.

## Counting unit and identity

Retain the existing guard's position-slot meaning: one nonzero broker instrument-side slot counts once, rather than one slot per trade ID. Multiple same-side trades in one instrument count as one slot. This choice needs explicit operational review because a trade-count interpretation would change current policy.

Use an exposure partition `(broker venue, environment, account identity)`. Practice and real accounts are distinct. Require an explicit expected partition supplied by the caller; never discover credentials or infer account identity from an unqualified instrument key.

Within a partition, use `(canonical instrument, BUY/SELL)` as the slot key. Use validated broker trade IDs as supporting identity evidence, scoped to that partition. Trade IDs must not replace the slot key or multiply the count. Normalize instruments through the established symbol parser; reject unknown symbols, nonfinite values, invalid sides, and contradictory signed units. Count only nonzero positions.

A managed broker-backed row must carry verifiable partition and slot identity. Missing metadata makes the view uncertain; it does not justify guessing an account. A synthetic paper row needs no broker identity because it is excluded first.

## Deduplication and source precedence

Build an immutable exposure view from one atomically captured snapshot generation and one consistent managed-book revision. Do not concatenate dictionaries or merge snapshots of different generations.

- A validated broker observation supplies broker quantity and side for its slot. A matching managed row contributes provenance, not another count.
- Matching trade IDs strengthen the match. Disjoint same-side trade IDs can still belong to one instrument-side slot; a complete broker slot's trade-ID set must cover any claimed currently open managed trade IDs.
- An unknown managed trade ID, incompatible quantities at a claimed common revision, or conflicting side is a conflict unless an explicit, validated temporal relationship explains it.
- Aggregate observations without trade IDs are acceptable for exposure only when complete slot identity and an unambiguous nonhedged instrument row are available. They confer no trade-level authority.
- Duplicate normalized broker instrument rows are rejected, even if identical. Do not silently collapse malformed snapshot payloads.
- Managed broker-backed slots not covered by the accepted complete snapshot require an ordered, synthetic-testable proof that their creation occurred after that snapshot. Count such slots once, marking that the snapshot needs refresh. Without that proof, block new risk. An old managed row cannot override a newer complete broker-flat snapshot or silently disappear; the disagreement is a conflict.
- If a managed-book revision changes during view construction, retry against a consistent revision a bounded number of times, then block new risk.

Do not mutate either registry when building or consuming this view. A symbol-only observation dictionary is insufficient as the long-term identity store; partition and snapshot generation must be explicit.

## Snapshot freshness and ordering

No production freshness budget is approved. The previous proposed 300-second default is withdrawn: an existing reconciliation default is not evidence that a broker snapshot remains complete for that interval. Offline tests use an injected budget B (for example 10 synthetic seconds), which has no operational standing.

A complete positions response establishes an observation at a broker-defined cut, if that cut is documented; it does not guarantee that no fills, external trades, closes, or pending-order executions occurred afterward. A local age bound cannot provide that guarantee. Before approving any positive budget, document the endpoint's atomicity, pagination and watermark semantics; cache/delivery delay guarantees; broker transaction coverage through reservation and dispatch; other writers to the account; and approved maximum exposure uncertainty. Use official endpoint documentation or controlled offline evidence, with no live/practice requests in this task. None of those guarantees has been established here. Budget approval must identify its evidence and risk rationale, not merely a matching default.

A positive age budget is necessary but insufficient. Entry also requires validated continuity of broker-event coverage from the snapshot cut through the decision boundary, or an explicitly approved alternative account-writer/consistency contract. Unknown coverage blocks entry. Setting the budget to zero does not repair absent continuity. Until endpoint semantics, continuity, and a budget are approved, use `EXPOSURE_FRESHNESS_POLICY_UNAPPROVED` and deny new broker risk.

Require request generation, response acceptance generation, request-start monotonic time, acceptance monotonic time, completeness classification, and partition identity. Require broker as-of time when the endpoint provides it, but do not invent a server timestamp when it does not. Without server as-of time, label freshness as local observation freshness, not broker-event completeness.

Compute age conservatively from request start using an injected monotonic clock, so a slow response cannot reset an old observation's age. A valid view has age in `[0, budget]`; age greater than budget is stale. Future server timestamps beyond an explicitly injected tolerance, negative monotonic age, and unknown clock provenance block new risk. Proposed server-future tolerance is zero pending review.

Issuing a newer refresh immediately and atomically changes the partition state to REFRESHING and invalidates the previous view for admission and dispatch. This transition uses the same coordinator as reservations. Old data remains last-known evidence only. Only the latest issued generation may publish; an older response cannot overwrite a newer response, in-flight state, or failure. Acceptance of a complete validated latest response atomically restores validity only after freshness, event continuity, managed-state consistency, and reservation reconciliation all pass. Failure, timeout, cancellation, or incomplete response leaves the partition invalid until a later complete valid refresh.

Existing reservations are not silently discarded. A never-dispatched RESERVED intent becomes FROZEN on refresh issue and cannot dispatch. On failure it remains FROZEN and continues occupying conservative capacity; it can be cancelled/released only through an atomic proof that dispatch never began. A DISPATCHING, ACKNOWLEDGED, or OUTCOME_UNKNOWN intent cannot be revoked locally: retain its full possible exposure, block new entries, and reconcile via authoritative broker evidence. Do not cancel broker orders or close positions. On successful refresh, revalidate each frozen reservation against the new view and its current capacity before allowing dispatch; do not automatically reactivate it. Process loss or missing reservation records makes the partition uncertain and denies entry until an approved recovery path establishes all outstanding intents. This proposal does not implement that recovery.

Reservation is a linearizable admission transaction, not a check followed by a separate write. It validates partition, accepted generation, validity, freshness policy, event coverage, managed revision, and reservation revision, computes capacity, and inserts an intent under one serializable per-partition coordinator. All processes capable of submitting orders for that partition must participate; a process-local lock is insufficient. An unavailable coordinator, unregistered writer, or unprovable state denies entry. No broker request is made while holding this transaction.

Before dispatch, atomically revalidate the reservation and transition it from RESERVED to DISPATCHING under that same coordinator. Refresh issue and this transition are serialized. If refresh wins, dispatch is forbidden. If dispatch wins, refresh must treat the intent as possibly in flight. A subsequent refresh cannot undo a network operation already authorised; its risk was already reserved. Unknown dispatch outcome remains counted. Source integration and any persistence/recovery mechanism require separate approval.

## Atomic capacity including pending reservations

Keep the reported broker/managed `same_direction_count` separate from `pending_direction_slots` and `effective_direction_count`. Both required discovery examples still report **1**. Admission uses the effective count, never the reported count alone.

For each USD direction, effective count is the cardinality of the union of validated occupied slot keys and all possible nonterminal reservation slot keys in the partition. Unknown identities invalidate the view. Pending orders that could create a slot must be linked to an intent or explicitly represented as external pending exposure; an unexplained order blocks admission. Multiple intents for an unoccupied identical slot contribute one possible slot under the approved slot policy; their quantities are outside this guard's scope and remain subject to other existing limits. Opposite-side intents on the same instrument are ambiguous under the nonhedged contract and deny admission until resolved; never assume netting or a close releases capacity.

For a proposed intent, atomically insert its slot into that union and permit reservation only if the resulting count is at most the configured limit. Preserve the existing deny-at-limit policy for any additional same-direction entry when effective count is already at the limit, including an already occupied slot. Thus this proposal does not authorise scaling at the cap. An idempotency key binds partition, instrument, side, and intent payload: retrying the same key returns its original reservation, while reusing it for a different payload denies.

With one observed LONG-USD slot and limit 2, two different-slot LONG-USD candidates racing at a barrier cannot both reserve. In either deterministic serialization, the first succeeds and raises effective count to 2; the second fails without dispatch. The reported observed count stays 1. A read-only preview grants no capacity.

Reserved capacity is released only by a proven never-dispatched cancellation, authoritative terminal rejection/cancellation establishing no remaining exposure, or atomic transfer to a matching observed/managed fill. Partial fills retain the union of filled and still-possible slots; do not release on timeout, TTL expiry, lost acknowledgement, thread shutdown, or refresh failure. Converting a reservation into a broker slot and removing its pending representation occurs atomically, preventing a capacity gap or double count. Uncertain terminal outcomes block entry and retain possible exposure. External writers can exceed a local cap; absent a validated single-coordinator writer contract or approved coverage mechanism, the coordinator cannot claim a global guarantee and must deny admission.

## Broker-event ordering proof

Local wall times, monotonic request/receipt times, managed insertion times, HTTP response order, trade open-time strings, and lexicographic IDs are not proof that a fill occurred after a snapshot.

An acceptable proof requires a broker-defined account-scoped ordering domain and epoch; a snapshot watermark W explicitly guaranteed to describe all applicable position events through W; a validated fill event F in that same domain with F > W; and verified complete, ordered event coverage from W through the current cut, including cancellations, closes, corrections, and pending orders. Bind the fill to partition, instrument, side, trade ID and originating intent where available. Document comparison semantics; a response's last transaction identifier is not automatically a snapshot watermark. Detect gaps, epoch resets, duplicates with conflicting payloads, and intervening terminal events. A fill followed by a covered close does not remain open simply because F > W.

Only under these guarantees may an event-folded post-snapshot open slot supplement a snapshot. F <= W with an unexplained absent slot is a conflict; incomparable ordering, missing watermark, gap, or undocumented endpoint relationship is `EXPOSURE_ORDERING_UNPROVEN` and denies entry. If the positions endpoint cannot supply such a cut, do not enable the supplement path. Obtain an approved coherent broker-state mechanism in a separately authorised implementation. Fixtures may model the guarantees but cannot establish that the real endpoint provides them.

## Incomplete, failed, and empty snapshots

Distinguish complete nonempty, complete empty, incomplete, malformed, failed, stale, and conflict states. A missing positions field is incomplete, not empty. Endpoint/schema guarantees must establish completeness; if completeness is unknown, deny entry. Partial pages and unvalidated pagination cannot publish a complete view.

A complete empty snapshot can establish zero broker slots only when fresh, partition-valid, and consistent with managed state. It replaces the prior accepted observation generation; do not retain an old observation as current merely because its instrument was omitted. Historical evidence may be retained separately, labelled historical, without influencing a valid current count.

Incomplete or failed refreshes do not delete last-known evidence or fabricate broker-flat state. Retain diagnostic last-known slots, but mark them nonauthoritative for permitting entry. A last-known count is not a valid exposure count. A complete refresh is required to recover validity.

## Conflicts and explicit fail-closed behaviour

Conflicts include wrong partition, trade ID claimed by incompatible slots, ambiguous hedged long/short state, duplicate instrument rows, unsupported symbols, inconsistent side/units, managed/broker identity mismatch, unexplained disappearance, and mixed-generation data.

Return a structured decision containing `valid`, `entry_allowed`, `reason`, partition, snapshot generation, managed revision, age, count unit, and supporting slot provenance. For invalid views, the operative `same_direction_count` is unknown/null, `entry_allowed=False`, and a distinct `last_known_count` may be supplied for diagnostics. Consumers must handle invalidity before numeric cap logic; null must never coerce to zero. Legacy integer-only consumers must deny until adapted.

For a valid view, count slots whose USD direction matches the candidate using the established base/quote mapping. A candidate GBP_USD SELL and an observed EUR_USD SELL both mean LONG USD. With limit 2, count 1 leaves the direction guard within its limit; other gates still decide eligibility. Count 2 denies a third same-direction entry. Limit 0 disables the numeric cap only; it does not bypass snapshot/identity validity. A non-USD candidate has no USD count but still cannot bypass an invalid broker exposure view at the entry boundary.

Use stable reason codes, proposed as `EXPOSURE_SNAPSHOT_MISSING`, `EXPOSURE_SNAPSHOT_STALE`, `EXPOSURE_SNAPSHOT_INCOMPLETE`, `EXPOSURE_SNAPSHOT_FAILED`, `EXPOSURE_SNAPSHOT_MALFORMED`, `EXPOSURE_PARTITION_MISMATCH`, `EXPOSURE_IDENTITY_CONFLICT`, `EXPOSURE_VIEW_CHANGED`, and `USD_DIRECTION_LIMIT`. Diagnostics must contain no credentials.

## Worked examples

### Discovery only: required count 1

Synthetic partition A has a fresh complete snapshot containing EUR_USD SELL 2 units, trade T1. Managed positions are empty. A GBP_USD SELL candidate sees one LONG-USD slot. Count is **1**. T1 remains an observation; the managed book stays empty and no management callback runs.

### Window-paper overlap: required count 1

The same broker snapshot is present, while local EUR_USD window-paper SELL occupies the symbol key. Exclude paper, then count the broker slot. Count is **1**. Preserve the paper object unchanged and preserve the separate observation-only broker record. Do not displace paper or import the discovery into managed state.

### Managed and observed duplicate

A managed EUR_USD SELL row and snapshot both identify partition A, T1, 2 units at the same ordered revision. They represent one slot: count 1, not 2. Existing authority on the managed row is neither expanded nor copied to the observation.

### Multiple trades, opposite direction, and conflict

T1 and T2 are both EUR_USD SELL in partition A: one LONG-USD slot. An additional GBP_USD SELL slot makes count 2 and denies another LONG-USD entry at limit 2. EUR_USD BUY instead contributes SHORT USD and zero to a valid LONG-USD count. If T1 is simultaneously claimed as EUR_USD SELL and GBP_USD BUY, reject the view; do not pick a row or report zero.

### Failure after a good response

Generation 10 reports one slot. Generation 11 times out after issue. Retain generation 10 as last-known evidence, but deny new risk with `EXPOSURE_SNAPSHOT_FAILED`. Generation 12, complete and fresh, is required to regain validity. No timeout clears observations or permits entry.

### Flat snapshot and managed disagreement

A newer complete empty snapshot with no managed claims yields a valid zero. The same snapshot with an older allegedly open managed T1 yields identity conflict until reconciled through an approved path. Neither automatic deletion nor new management authority is implied.

## Deterministic offline test matrix

Run these proposed tests only in a separately verified offline harness with disposable synthetic fixtures. They are specifications, not claims of executed checks. Fix partition A/B, environment, candidate, limit, monotonic time, generations, and managed revisions per case. Default candidate is GBP_USD SELL, limit 2, injected fixture budget B=10 seconds, and a fresh complete partition-A snapshot with synthetic approved policy and gap-free event coverage. These approvals exist only inside fixtures.

1. No managed rows; observed EUR_USD SELL T1: valid, count **1**, observation-only, managed book empty. Preserve the first named count-one assertion.
2. Window-paper EUR_USD overlap plus observed T1: valid, count **1**, paper identity and all fields unchanged. Preserve the restart-window count-one assertion; remove no assertion by substituting zero.
3. Paper-only book plus complete empty broker snapshot: valid count 0; no broker authority created.
4. Matching managed/observed T1: valid count 1; provenance records both sources; neither row mutated.
5. Two same-side EUR_USD trades in one complete slot: count 1. Separate EUR_USD and GBP_USD SELL slots: count 2, entry denied by limit.
6. EUR_USD BUY observation: valid LONG-USD count 0 and SHORT-USD count 1.
7. Wrong account, wrong venue, or practice/real mismatch: invalid, unknown operative count, partition-mismatch denial; no cross-partition merging.
8. Aggregate slot with no trade IDs, unambiguous side and complete snapshot: count 1; management forbidden. Unknown managed claimed ID not covered by complete snapshot: conflict denial.
9. Duplicate canonical instrument rows, including identical duplicates: malformed denial. One trade ID mapped to incompatible slots: identity-conflict denial.
10. Both nonzero long and short for one instrument under current nonhedged interpretation: conflict denial; do not net to zero. Zero units in a valid row: contributes no slot.
11. NaN/infinity, invalid sign/side, unsupported symbol, or missing partition: deny; operative count unknown.
12. Age exactly B: valid with coverage. Age B plus one injected clock tick: stale denial. Negative age or future server time beyond explicit tolerance: deny.
13. Request starts at 0 and completes at B+1: stale immediately despite acceptance at B+1. No server timestamp: use documented local request-age semantics.
14. No accepted snapshot: missing-snapshot denial. Missing positions key or partial page: incomplete denial. Malformed payload: malformed denial.
15. Refresh timeout/error after a valid one-slot generation: retain last-known count 1, operative count unknown, entry denied. Subsequent fresh complete generation restores validity.
16. Newer complete empty snapshot, no managed claims: valid count 0 and old observation excluded. Same empty snapshot with older managed T1: conflict denial.
17. Generation N responds after N+1 issues or fails: N cannot publish or restore validity. A later complete latest generation may do so.
18. Proven post-snapshot managed broker fill in a new slot: count once in addition to snapshot slots, provided the ordering proof is valid. Missing proof or ambiguous overlap: deny.
19. Managed revision or snapshot generation changes before atomic reservation: re-evaluate; bounded retry exhaustion denies. No reservation occurs using an invalidated view.
20. Cap 0 and invalid snapshot: deny. Valid non-USD candidate plus invalid view at entry boundary: deny. Valid count 1 at cap 2 does not bypass any other gate.
21. Repeated evaluation, permuted input order, and repeated identical accepted evidence produce identical decisions and no registry mutations. Reset observations, revisions, and generations between tests.
22. For every case, instrument management/order callbacks, committed reservations on denied paths, persistence, and transport calls: zero unexpected calls. Observation-only records never become eligible for management before or after evaluation.

### Additional deterministic concurrency and evidence cases

23. Two different-slot candidates start from observed count 1, cap 2, and identical preview revision. Force A-before-B and B-before-A coordinator schedules: exactly one committed reservation in each; effective count 2; reported count 1; losing candidate never dispatches. Include separate simulated process clients sharing one fake coordinator.
24. Same idempotency key retried concurrently creates exactly one intent. Different payload with that key denies. Distinct same-slot intents deduplicate capacity under slot semantics; scaling at an already reached cap still denies. Opposite-side same-instrument intents deny as ambiguous.
25. Coordinator unavailable, independent process-local coordinators, unregistered external writer, or missing reservation state: deny. No test may claim a global guarantee from a local mutex.
26. Serialize refresh issue before reserve and before dispatch: both deny while REFRESHING. Serialize DISPATCHING before refresh: intent remains counted as possibly in flight, with no second admission. Use barriers/events and a fake dispatcher, never sleeps or real transports.
27. Refresh failure after one RESERVED and one DISPATCHING intent: first freezes, second remains unresolved, neither loses capacity; no subsequent dispatch/admission. Proven never-dispatched cancellation releases only the frozen intent. Success alone does not reactivate it.
28. Timeout, TTL expiry, lost acknowledgement, and worker stop do not release possible capacity. Partial fill and pending remainder count their slot union once. Authoritative rejection with no fill releases capacity; contradictory rejection/fill evidence denies. Atomic reservation-to-fill transfer has no observable zero-capacity gap.
29. Snapshot watermark W=100, verified fill F=101, gap-free stream through 102: supplement the open slot once. F=100, missing W, account/epoch mismatch, undocumented watermark semantics, and gap at 101 each deny. An intervening close at 102 removes the open slot only through validated folding, not a local timestamp.
30. Local timestamp after request/response, broker open-time text, and response arrival order without watermark proof: all deny supplementation. Reversing timestamps cannot change that result.
31. Missing freshness approval denies even with age zero. Approved synthetic B with broken continuity denies within B. No server as-of time must not be labelled broker-event freshness. A legacy configured 300 seconds cannot grant approval.
32. At the atomic boundary, inject a generation, coverage, managed revision, or reservation revision change: retry or deny; never commit against stale capacity. Run bounded exhaustive interleavings of reserve, refresh, dispatch, cancel, fill-transfer, and failed response; every accepted transition preserves the cap for coordinated admissions and observation authority invariants.
33. Source-seal acceptance specification: compare raw bytes against the required R.86 hash before any proposed integration. Mismatch blocks implementation acceptance. A document approval is not a seal exception; no test repair may silently update the expected hash.

These are documentation-only test additions. No executable tests have been added or run for this revision.

The harness must block sockets, DNS, HTTP transports, subprocess escapes, PostgreSQL connection entry points, dotenv loading, and reads/writes outside explicit source allowlists and disposable fixture directories before application imports. Verify each barrier with a sentinel that fails if reached. Use an environment allowlist without printing inherited values; fake broker/account dependencies only. Do not run unrestricted main.py/run_bot, install packages, access production journals/databases, or touch permit/consumed-marker files. Fixtures must not write existing research/scheduler outputs. If isolation cannot be established, do not run application tests.

## Proposed source changes, not implemented

- `forex_bot/positions.py`: retain observation-only storage and management exclusion; introduce explicit partition/generation metadata or a dedicated immutable observation representation. No management adoption.
- `forex_bot/reconciliation.py`: publish complete snapshots atomically with freshness, ordering, failure state, and explicit completeness; replace current-generation observations on valid complete refreshes without mutating managed positions.
- Proposed new `forex_bot/exposure_view.py`: pure validation, partition checks, slot identity, deduplication, immutable provenance, and structured validity decisions.
- `forex_bot/portfolio_exposure.py`: consume the validated view for USD-direction counting; preserve base/quote mapping and slot-count policy; propagate unknown exposure without treating it as zero.
- Proposed reservation coordinator and existing order-intent integration (exact file locations to be reviewed): atomic admission, intent lifecycle, refresh serialization, dispatch validation, and fill-transfer deduplication. No actual coordinator, persistence, recovery, or database changes are authorised here.
- `forex_bot/bot_loop.py`: **no proposed edit under the current authorisation**. It is sealed operational source. Required R.86 raw SHA-256 is `a2310a7f2d2aee4b60c3c471cdd56ed48c72e2ed29232047c404209537e58d81`; the inspected local hash is `2f1c36dc025d114685e4424402f6866c66aa6eb37d28717027c502a4f447118d`. The existing mismatch is unresolved, not permission to modify or restore the file. Any integration requiring a sealed-source change needs separate explicit authorisation identifying exact edits, an approved new seal/baseline process, and required regression checks. Preserve the current local bytes. Approval of this document alone cannot grant that exception. If integration cannot satisfy the seal, stop rather than route around the restriction through another module.
- Actual startup/cycle/reservation callers: read-only integration review only until the seal and operational-source scope are separately authorised. No startup recovery implementation or gate-configuration changes.
- `tests/test_reconcile_conflict.py` and proposed dedicated exposure-view tests: preserve both count-one expectations, replace obsolete management-import expectations with observation-only invariants, and implement the matrix in disposable offline fixtures. Test-helper repairs from cloud require separate comparison; do not assume they are present.

Do not broaden this patch to gross-notional caps, signed-exposure reports, broker close recovery, strategies, sizing, SL/TP, R.87 recovery implementation, or R.88. Audit other consumers for compatibility, but any policy expansion requires its own review.

## Review decisions and acceptance

Approve or revise the slot-count unit, atomic cross-process coordinator/writer contract, reservation lifecycle, immediate refresh invalidation, broker ordering proof, partition metadata, structured unknown-count handling, and server-time tolerance before source work. Freshness budget and continuity remain unapproved pending broker semantic evidence. Resolve the existing source-seal mismatch and obtain separate explicit authorisation for any sealed-source exception. Endpoint completeness guarantees and actual caller compatibility must be verified during that review. No operational-source or executable-test edits are authorised by this revision.

Implementation acceptance requires all matrix cases passing in verified isolation, both required counts remaining 1, no added management authority, appropriate focused and broader checks with explicit unresolved failures, and preserved pre-existing work. This document is not a trading release approval. Required checks are currently missing; no commit or push while required checks fail, are pending, or are missing. Production remains **NO-GO**.

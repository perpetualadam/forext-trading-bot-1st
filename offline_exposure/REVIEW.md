# R.87C offline implementation and integration review

2026-10-26. Production remains **NO-GO**. This is an offline prototype with no production caller, persistence, broker adapter, or authority path. Stop here for review; no commit or push.

## Workspace and wrapper decision

Started on `main`, HEAD `883752f91510f639d354f090331446dcc6ade0a8`. Existing modified scheduler `audit.jsonl` and `state.json` were identified by status only; their contents were not read or edited in this phase. The existing untracked `EXPOSURE_CONTRACT_PROPOSAL.md` was preserved. No existing source was modified; `forex_bot/exposure_view.py` and the `offline_exposure` directory are new.

The source-only R.86 archive contains `forex_bot/bot_loop.py` with raw SHA-256 `a2310a7f2d2aee4b60c3c471cdd56ed48c72e2ed29232047c404209537e58d81`, exactly the required seal. The current local file still hashes to `2f1c36dc025d114685e4424402f6866c66aa6eb37d28717027c502a4f447118d`. A line comparison confirms only the added module wrapper and moved import boundary; raw bytes, not normalized text, were used for both hashes.

Restoration was **not performed**. Consumers still patch the removed seam in `test_decision_repair_f1.py`, `test_decision_repair_f2.py`, `test_g8_missing_candles.py`, `test_g9_1_candle_exceptions.py`, `test_g9_management.py`, and `test_ohlcv_off_event_loop.py`. The conditional restoration's consumer precondition therefore fails. The cloud patch repairing those consumers is absent. Do not change the expected seal. A passing conflict-detection test below means the conflict was correctly detected, not that the operational seal passes. Consumer migration and its isolated checks must be reviewed before restoring exact archived bytes. A changed R.86 implementation would instead require a new baseline review.

## Implemented boundaries

`forex_bot/exposure_view.py` uses only standard-library dataclasses and numerical validation. It accepts immutable synthetic evidence, returns a structured validity result and deterministic slot provenance, and performs no I/O or application imports. Default policy is unapproved and returns unknown count, never zero. No production module imports it.

It models partition identity, symbol normalization against an injected allowlist, instrument-side slot counting, trade-ID conflict checks, managed/observed deduplication, paper exclusion, empty/failed/incomplete/stale generations, and a simplified full-slot OPEN/CLOSE evidence fold. Unlinked external pending orders and unknown pending-order coverage explicitly deny. A valid decision's count is a read-only preview, never order permission. Both required synthetic scenarios count **1** while observations stay immutable and observation-only. Existing operational tests have not been edited or executed.

The model deliberately has no management methods. An observation is never inserted into the managed registry, nor can it trigger adoption, paper displacement, SL/TP/MFE changes, closing, or resizing. Caller-provided evidence and approval booleans are trusted fixture claims, not authentication of broker evidence. The model is not a JSON parser or broker adapter.

`offline_exposure/fake_coordinator.py` serializes reservation, refresh, simulated dispatch authorization, unsent cancellation, and fill transfer with one in-memory RLock. It counts the union of occupied and possible pending slots; preserves reported broker count separately from capacity; binds idempotency keys to payload; freezes unsent intents on refresh issue; keeps dispatched intents counted on refresh failure; and does not release unknown outcomes by time. Clock/deadline are injected simulation inputs. Its successful dispatch method returns a boolean only; it has no network callback.

**Verified simulation:** both deterministic candidate orders and a barrier-started two-thread race admit exactly one additional distinct slot from count 1 at limit 2. Enumerated reserve/refresh/dispatch schedules remain within that simulated cap. **Not verified cross-process:** separate fake instances both admit, producing a three-slot union. An executable counterexample documents that limitation. There is no persistent coordinator, interprocess locking, restart state, external-writer fencing, or crash guarantee. No real processes were spawned by the tests.

## Official broker documentation research

Only public documentation pages were retrieved; no account, real/practice API, stream, or order endpoint was called. Documentation checked on 2026-10-26.

- OANDA describes Account Details as a complete, consistent starting account state and prescribes repeated Account Changes polling to maintain it. This supports investigating that paired protocol rather than assuming independent positions and orders calls share a cut. It does not approve a 300-second age budget. [OANDA Best Practices](https://developer.oanda.com/rest-live-v20/best-practices/)
- Account Details includes pending orders, open trades, and positions. Account Changes accepts `sinceTransactionID`; its returned last transaction ID is the cursor through which changes have been observed. Adapter validation must still handle response errors, cursor failures, schemas, and interrupted update chains. [OANDA Account Endpoints](https://developer.oanda.com/rest-live-v20/account-ep/)
- OpenPositions documents an array of open positions plus the latest account transaction ID; no pagination parameter is listed for this operation. This supports its advertised list scope but does not independently establish equivalence to the Account Details/Changes protocol or continuity at a later reservation instant. [OANDA Position Endpoints](https://developer.oanda.com/rest-live-v20/position-ep/)
- Transactions support history retrieval, including page-based queries; the stream begins at request time and emits heartbeats. A newly opened stream is not by itself proof that a prior snapshot-to-stream gap was filled. [OANDA Transaction Endpoints](https://developer.oanda.com/rest-live-v20/transaction-ep/)

Inference and remaining gaps: these sources support a cursor-based account mirror as an integration candidate. They do not establish an atomic broker-side exposure admission operation or a positive freshness budget safe against other writers and pending orders. Do not treat a heartbeat, HTTP arrival order, local timestamps, or an arbitrary `lastTransactionID` field as sufficient ordering proof. The synthetic event model's contiguous integers are its own fixture protocol; it makes **no claim** that real OANDA transaction IDs are numerically adjacent. A real adapter must establish documented coverage without that assumption and validate correction, partial-fill, cancellation, account/epoch, and trade lifecycle semantics.

Freshness policy remains **unapproved**. The fixture budget of 10 seconds is for boundary tests only. Endpoint evidence above does not close the interval between a poll response and broker dispatch. That interval, all account writers, outstanding pending orders, and accepted risk uncertainty still require an approved contract. Default evaluation stays fail closed.

## Executed checks and isolation

Run from repository root:

```powershell
python -I -S -B offline_exposure/run_checks.py
```

The runner bypasses pytest and its application-importing conftest, disables site packages and bytecode, clears the process environment without printing values, and installs audit barriers before loading the project modules by exact file path. Reads are limited to the new source/test files, the sealed-source file and its R.86 archive, and Python's standard library. Writes and filesystem mutations are denied. Sockets, subprocesses, native library loading, dotenv, PostgreSQL, HTTP client modules, and application package imports are blocked. Sentinel checks exercise the barriers using synthetic audit events, without touching prohibited files or initiating operations. This is a guard for trusted offline tests, not an adversarial operating-system sandbox.

First implementation run: **34 tests, 0 failures, 0 errors, 0 skips**. After adding pending-order fail-closed cases, default-policy checks, actual source seal conflict detection, and the independent-coordinator counterexample: **37 tests, 0 failures, 0 errors, 0 skips**. Final verification after malformed-type handling and expanded assertions: **37 tests, 0 failures, 0 errors, 0 skips** (0.023 seconds reported by unittest). No existing operational/full suite was run, and these results do not supersede the historical unresolved suite failures.

Read-only inspection encountered a Windows console `UnicodeEncodeError` while printing the first source diff; rerunning with ASCII-safe JSON completed the comparison. A source search also named nonexistent `forex_bot/main.py`; the actual startup module was subsequently identified as `forex_bot/app.py`. These were inspection errors, not test failures, and no source restoration followed them.

## Mapping to the 33-case design matrix

Executable tests 01–33 follow the design case numbering; 34–36 add explicit conservative pending-order handling, default refusal, and the independent-coordinator counterexample. The runner adds one isolation test. One numbered test can contain multiple assertions or subcases; 37 tests is not proof of full contract implementation.

- Cases 1–11: synthetic partition/slot/trade identity, count-one examples, paper exclusion, aggregate identity, malformed numbers/sides, duplicates, and conflict refusal are covered. Real instrument/account schema validation remains an adapter obligation.
- Cases 12–14: injected request-age boundaries, slow/clock-invalid responses, and classified snapshot failures are covered. Broker server timestamps, payload parsing, pagination and completeness classification are not implemented; this module consumes typed classified evidence.
- Cases 15–17: failed refresh, flat/managed conflict, and obsolete generation refusal are covered. Last-known data remain in the fake but cannot authorize dispatch.
- Case 18: synthetic broker-watermark/event proof and missing-proof refusal are covered. Real broker ordering, corrections, and arbitrary transaction folding are not verified.
- Cases 19–22: stale reservation revision refusal, invalidity despite cap zero/non-USD candidate, deterministic input order, and absence of authority methods are covered. No real reservation boundary or management callback is wired, so production callback suppression is not demonstrated.
- Cases 23–27: serial schedules and actual threads sharing one fake lock, idempotency payload binding, cap refusal, unavailable/unapproved writer, refresh/dispatch order, and frozen/dispatched retention are covered. Multi-process clients, external writer fencing, and lost-process records are not implemented.
- Case 28: dispatched capacity cannot be released as unsent; atomic synthetic fill transfer has no capacity gap. Partial fills, terminal broker rejection/cancellation proof, durable tombstones, and recovery after shutdown are not implemented. Unknown evidence must not use the transfer/release methods as proof.
- Cases 29–31: synthetic cut/epoch/sequence gaps, subsequent close folding, missing order proof despite local time, and missing policy/continuity approval are covered. Real endpoint semantics and freshness approval remain absent.
- Case 32: fake clock expiration, stale revision, and all six permutations of reserve/refresh/dispatch are covered. This is not exhaustive model checking of all lifecycle transitions or a real snapshot-to-dispatch freshness guarantee.
- Case 33: actual archive hash passes the existing seal, while actual local hash mismatch is detected and the local bytes remain unchanged. Seal acceptance itself remains blocked.

Any unsupported broker state must be rejected by a future adapter rather than approximated into this model. Frozen reservation reactivation is intentionally absent: a successful refresh does not restore dispatch automatically. No executable test is marked skipped to conceal these omissions; they are explicit scope/evidence gaps.

## Production integration proposal — disabled

Read-only candidate integration points, not authorisation to edit them:

1. `reconciliation.py`: `fetch_broker_positions_detail`, `_begin_snapshot_request`, `_publish_snapshot`, `_apply_position_convergence`, and `reconcile_positions_log_only`. A future approved account-mirror adapter should publish one coherent immutable generation and invalidate admission immediately on refresh issue, preserving observation-only ownership. Independent fetches must not manufacture a coherent cut.
2. `positions.py`: observation and managed-book adapters need explicit account/environment identity, canonical slot and broker trade metadata, plus an immutable managed revision. Never convert observations into authority-bearing rows.
3. `portfolio_exposure.py`: adapt existing direction-count consumers to structured invalidity and diagnostic/provenance fields. Never coerce unknown count to zero or mistake a preview for capacity.
4. `bot_loop.py`: direction checks exist around lines 1661 and 4030; the injected iteration's `try_begin_order_submission` call follows around line 4268. These are separate stages today. Any change is blocked by the unresolved seal/consumer conflict and needs review of both real and synthetic call chains, not just the injected iteration.
5. `database.py`: `try_begin_order_submission`, current-intent tracking, and release/update functions are candidate lifecycle contracts only. No database imports or connections occurred. Existing process maps and a Python lock cannot establish account-wide exposure safety. Production coordinator storage is explicitly out of scope.
6. `oanda_exec.py`: `_submit_order_create` and `execute_oanda_market_open` identify dispatch boundaries to audit after explicit integration approval. Every order-creation path would need the same validated intent transition; this phase proves none of those paths are fenced.
7. `app.py`: `initialise_application`, startup exposure evaluation, reconciliation loop and lifespan launch of `run_bot` need a coherent readiness contract. No startup/lifespan code was executed or changed.

Before any cross-process claim, define a concrete serializable per-partition coordinator with conditional generation/revision checks, idempotency retention, dispatch leases/fencing semantics, and atomic intent-to-fill transfer. All account writers must participate or be covered by an approved external-change policy. A crash after authorization but before/after send must retain uncertainty. Choose storage, isolation and ownership explicitly in a subsequent design review; do not infer them from this fake. No production persistence, restart recovery, R.87 recovery, or R.88 is implemented here.

Review prerequisites remain the broker adapter's evidence contract, explicit freshness/writer approval, an actual coordinator design, sealed-boundary consumer repair/restoration, and later integration verification. Existing gates/permits/markers were not altered. Production remains **NO-GO**.

## Follow-up: occupied-slot OPEN and malformed numeric inputs

The review identified a real defect in the earlier simplified event fold: OPEN of T2 in an occupied instrument-side slot replaced T1, allowing a subsequent exact CLOSE of T2 to report zero while T1 was still open. The prototype now rejects **every OPEN into an occupied slot**, including an apparent duplicate. It returns `EXPOSURE_IDENTITY_CONFLICT` with an unknown operative count. It neither overwrites the slot nor proceeds to CLOSE. An OPEN into an empty slot followed by its exact CLOSE remains supported. Trade-level lifecycle merging and complete slot-replacement semantics remain unimplemented.

Regression test 37 exercises both OPEN T2 alone and OPEN T2 followed by CLOSE T2 against snapshot T1. Both must be invalid, never valid count zero; the original snapshot is unchanged and independently still counts 1. The two required original discovery examples also continue to count 1, without management authority.

Malformed numeric handling is explicit rather than coercive. Budget, local clock values, and units accept finite **builtin int/float only**; bool, strings, containers, complex values, nonfinite values, and integers that overflow `math.isfinite` conversion are rejected through a nonthrowing helper. Invalid budget returns unapproved freshness policy; invalid clocks return stale snapshot; invalid units return malformed snapshot. Generation and revision metadata require nonnegative builtin integers; watermark/coverage/event sequence violations return structured refusal. The row/event exception boundary also catches numeric overflow. The API still expects the declared evidence dataclass shapes and is not an arbitrary-object or JSON parser; there is no blanket guarantee for hostile custom objects. A future adapter must validate its own schema.

Tests 38 and 39 cover malformed numerics in clocks, budget, units, generation/revision metadata, snapshot watermark, coverage cursor, and event sequence. The initial regression run, before the fixes, ran 39 tests and reported **5 failing subcases, 24 errors, 0 skips**. Failures exposed the occupied-slot overwrite and bool acceptance; errors exposed TypeError and OverflowError from malformed numerics. After the first fix: **39 tests, 0 failures, 0 errors, 0 skips**. Final expanded run: **40 tests, 0 failures, 0 errors, 0 skips** (0.030 seconds reported by unittest), using the same isolated command documented above. These are locally executed, reported results, not independent verification by the reviewer.

This follow-up changes only the new pure model, its synthetic tests, and this report. The fake coordinator and runner are unchanged. Their source is available alongside this report as `fake_coordinator.py`, `run_checks.py`, and `test_contract.py`; the pure module is `forex_bot/exposure_view.py` relative to repository root, or `../forex_bot/exposure_view.py` from this report's directory. Wrapper migration/restoration remains separate; no production integration, commit, or push. Existing scheduler work was identified by status only and was neither read for content nor edited. Production remains **NO-GO**.


## Follow-up: conservative fill transfer and revision monotonicity

Review found that transfer_fill could replace the current occupied view with a same-generation view missing unrelated exposure. With observed EUR_USD and a dispatched GBP_USD intent, an incoming GBP_USD-only view could erase EUR_USD and free capacity incorrectly.

The fake now requires every existing occupied slot to be present in the incoming view, under the existing coordinator lock and before any mutation. This prototype has no validated terminal-evidence representation, so **all occupied-slot removals via fill transfer are rejected**. A valid incoming view flag alone is not terminal evidence. No terminal-removal exception or lifecycle implementation is added. Rejection leaves the current view, all intents, coordinator revision, and occupied-plus-pending slot union unchanged. The dispatched intent remains counted and a third same-direction reservation is refused.

Incoming managed-book revision must be a nonnegative builtin integer and at least the current view's managed-book revision. Equal revisions remain acceptable for this limited slot-only synthetic fold; a lower revision is rejected even if the incoming view contains every required slot. This does not establish richer content ordering at equal revisions. The coordinator's own mutation revision is a separate sequence: a successful transfer increments it once, while a refused transfer leaves it unchanged. Neither generation equality nor a greater managed revision permits dropping an unrelated occupied slot.

New tests 40 and 41 reproduce unrelated-slot loss and managed-revision rollback. Test 42 checks legitimate equal/increasing managed revisions, full retained exposure, atomic intent removal, exactly one coordinator-revision increment, retention of an unrelated pending intent, and refusal of a third LONG-USD slot. Test 43 rejects malformed manually constructed Decision revisions without mutating state.

The pre-fix regression run reported **43 tests, 2 failures, 0 errors, 0 skips**. After the fix it reported **43 tests, 0 failures, 0 errors, 0 skips**. Final expanded isolated run reported **44 tests, 0 failures, 0 errors, 0 skips** (0.022 seconds reported by unittest), with the same python -I -S -B offline_exposure/run_checks.py command. These remain locally reported results, not independent reviewer verification. Both original required counts remain 1, and observations gain no management authority.

This correction modifies only fake_coordinator.py, test_contract.py and this review document. The pure module, runner and wrapper are unchanged in this follow-up; the actual source-hash regression still passes its unchanged-local-bytes assertion. Existing scheduler modifications were identified by status only, without reading their contents. No production integration, broker operations, persistence/recovery work, commit or push. Production remains **NO-GO**.


## Follow-up: single-use refresh completion

The fake coordinator's publish() now requires both an active refresh and the current issued generation. refresh() alone opens a completion opportunity; the first success or failure consumes it by clearing refreshing under the coordinator lock. A publication with no active refresh, a duplicate completion, or a late success after failure returns False before changing any state. Only a new refresh, with an incremented generation, permits another completion. A late response from a superseded generation cannot consume the newer active refresh.

Tests 44–47 snapshot the view, intents, issued generation, coordinator revision, refreshing/failure flags, availability, deadline, slot union and validity before refused publications and assert equality afterward. They cover unsolicited success/failure, repeated success, exposure-dropping duplicate success, failure after success, success after failure, repeated failure, and old-generation publication during a new active refresh. A legitimate new-generation completion after failure updates the view and advances the coordinator revision exactly once; frozen reservations remain frozen and counted rather than gaining dispatch authority.

The pre-fix regression run reported **48 tests, 7 failing subcases, 0 errors, 0 skips**. The final safely isolated run reported **48 tests, 0 failures, 0 errors, 0 skips** (0.012 seconds reported by unittest), using python -I -S -B offline_exposure/run_checks.py. These are locally executed, reported results, not independent reviewer verification. Both required discovery counts remain 1 and observation-only management restrictions remain intact.

Only the offline fake coordinator, synthetic tests and this report changed in this follow-up. The pure exposure model, runner and wrapper were left unchanged. Existing scheduler files were identified through status only without reading their contents. No production integration, commit or push; production remains **NO-GO**.

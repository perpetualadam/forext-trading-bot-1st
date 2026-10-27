# Offline coordinator concurrency review

Classification: **OFFLINE_COORDINATOR_CONCURRENCY_PARTIALLY_VERIFIED**

Production trading remains **NO-GO**. No commit or push. This classification describes bounded thread schedules and synthetic evidence, not process safety, durable persistence, broker-side idempotency, or readiness to trade.

## Baseline and isolation

Working-tree source and existing tests were read before extending them. The actual pure-model path is `forex_bot/exposure_view.py`; `offline_exposure/exposure_view.py` does not exist. Initial baseline rerun: 48 tests, 48 passed, 0 failures, 0 errors, 0 skips, 0.012 seconds. Branch/HEAD remain the previously inspected `main` / `883752f91510f639d354f090331446dcc6ade0a8`; no git mutation occurred.

The two existing modified scheduler files and untracked proposal/model/offline files were preserved. Scheduler contents, credentials, `.env`, production journals/databases and consumed-marker contents were not accessed. The full pasted request was supplied after the initial baseline run; the before-integrity manifest was captured before development changes and the subsequent regression runs.

Environment: Python 3.13.5, MSC v.1943, AMD64; Microsoft Windows NT 10.0.26300.0. No dependencies installed.

All executable tests used the inspected `-I -S -B` runner: no site packages or pytest/conftest; environment cleared without disclosure; audited source-file read allowlist; writes/mutations denied inside tests; socket, subprocess, native-loader, HTTP, dotenv, PostgreSQL and application-package barriers installed before project code loads. Barrier sentinels are included in every run. Logs are written by the parent PowerShell process, outside the read-only test process. These are defenses for trusted synthetic tests, not an adversarial OS sandbox.

## Source findings and reproduced defects

All six coordinator mutations hold the same RLock across their checks and mutations: reserve, dispatch, refresh, publish, release_unsent and transfer_fill. `_valid()` and `_slots()` are internal unlocked helpers used under that lock by mutation methods. Tests read state only after worker completion or at explicitly ordered quiescent points. Mutable public attributes are trusted fixture state, not a protected external API.

Refresh policy is unambiguously **latest-generation-wins** in the existing source and prior regression contract: each refresh increments the issued generation, freezes unsent reservations and supersedes earlier requests. Reject-overlap would be a different contract and was not introduced. Python integer generations do not wrap at a fixed machine-word boundary.

Two genuine validation defects were reproduced:

1. `publish(1.0, ...)` and `publish(True, ...)` could match integer generation 1 because Python equality treats these values as equal. A malformed request token could consume completion and mutate the view/revision.
2. A valid same-partition, current-generation Decision with a managed-book revision lower than the current view could be published, despite rollback prevention in transfer_fill.

Minimal correction: require nonnegative builtin integer publication tokens before any state mutation. Validate current completion evidence as a Decision with a builtin integer generation, matching partition/generation, and a nonnegative builtin integer managed revision no lower than the current managed revision. No public method signature changed. Invalid current completion evidence consumes failure, preserving last-known view, intents and capacity; malformed/stale request tokens do not consume completion and leave all state unchanged. These are distinct cases.

The first extended pre-fix run had 55 tests, 8 failures, 0 errors, 0 skips, 0.041 seconds. Its malformed-input test reused state after the first bad float publication; subsequent failures were cascading state mismatches, not eight separate defects. After isolating each input and adding rollback coverage, the pre-fix run had 56 tests, 3 failures, 0 errors, 0 skips, 0.024 seconds: float token, bool token, and managed-revision rollback. The first post-fix run had 56 tests, 0 failures, 0 errors, 0 skips, 0.022 seconds. Logs preserve each result.

## Added deterministic regressions

ConcurrencyTests A–I supplement the original ContractTests without inheriting/repeating them. A worker helper uses a three-party barrier for two workers plus the test, five-second waits/joins, indexed result/error collection, explicit predecessor events for ordered schedules, and daemon workers so a detected deadlock cannot keep the interpreter alive. Worker exceptions fail the test. No random sleeps, broker callbacks or external services are used. Concurrent starts do not prescribe a winner; both specified winner orders are tested separately.

- A: two threads publish distinct valid views for one generation, both barrier-started and in each explicitly ordered serialization. Exactly one succeeds, revision advances once, the winning object remains installed, intents persist, duplicate replay is inert, and no worker remains alive.
- B: two refresh threads issue N and N+1 in order before any completion. Test both an initially healthy and initially failed coordinator. Stale success and stale failure preserve view, issued generation, refresh/failure flags, revision, occupied slots and frozen intents. N+1 completes once.
- C: explicitly order failure before a late-success thread. Failure consumes completion; late success cannot change any state or restore validity. Dispatch and new reservation remain denied. A later new generation succeeds without reactivating frozen intents.
- D: dispatch/refresh workers in both linearization orders. Dispatch-first retains DISPATCHING exposure; refresh-first freezes the unsent intent and refuses dispatch. Dispatch remains refused while refreshing and after failure. No previously dispatched intent disappears.
- E: reserve/refresh workers in both orders. Reserve-first commits once then freezes the intent; refresh-first refuses reservation without adding capacity. Original occupied exposure remains counted, and new reservations remain refused while refreshing.
- F: successive successful, failed, superseded and later successful generations. Delayed/duplicate responses preserve the full state snapshot, including revision. Dispatched intents and slot union survive every transition.
- G: independently test malformed generation tokens against an active generation 1, including float/bool equality traps. Every refusal preserves the active completion opportunity; the subsequent integer-token completion succeeds.
- H: current-generation managed-revision rollback consumes failure without publishing stale state or losing intents; a later generation at the retained revision can succeed.
- I: malformed manually constructed completion evidence fails closed without raising, clearing capacity, or accepting a late replacement for the failed completion.

State snapshots include view, intents, issued generation, coordinator revision, refreshing/failed flags, availability, deadline, slot union and computed validity. Revision changes are asserted for accepted state transitions; stale/out-of-phase refusals are asserted to be inert.

## Revision, generation and authority invariants

Issued generation and coordinator mutation revision are different counters. Every refresh advances each once; one accepted completion, successful or failed, advances mutation revision once. A superseded/malformed token, duplicate completion, refused reservation, or refused dispatch does not advance it. Managed-book revision is separate evidence metadata and is now nondecreasing on publish as well as transfer_fill.

One refresh completion is available only while refreshing is true for the latest issued generation. Completion clears that flag inside the lock. A failed generation cannot be revived; only a new generation opens a new opportunity. Idempotent reserve calls may return an existing frozen or dispatched intent record, which is not a new reservation or dispatch grant. Actual dispatch still requires RESERVED and a valid nonrefreshing, nonfailed coordinator. release_unsent cannot remove DISPATCHING state. transfer_fill retains prior occupied slots and unrelated pending intents under its existing conservative contract.

Both required discovery counts remain **1**. Observations gain no management authority. These tests do not establish that arbitrary manually constructed evidence reflects broker truth.

## Final commands and regression results

All durations below are unittest execution time, not parent-shell startup time. PowerShell capture suffix used for each logged run: `2>&1 | Tee-Object -FilePath <log> | Select-Object -Last <N>`.

1. `python -I -S -B offline_exposure/run_checks.py --concurrency`
   — 10 tests, 10 passed, 0 failures, 0 errors, 0 skips, 0.010 seconds; `FOCUSED_FINAL.log`.
2. `python -I -S -B offline_exposure/run_checks.py`
   — 57 tests, 57 passed, 0 failures, 0 errors, 0 skips, 0.020 seconds; `COMPLETE_FINAL.log`.
3. `python -I -S -B offline_exposure/run_checks.py --historical`
   — original regression group: 48 tests, 48 passed, 0 failures, 0 errors, 0 skips, 0.012 seconds; `HISTORICAL_FINAL.log`.

The focused and historical selectors are new optional runner arguments. The original command still runs the complete suite. Each selection includes the isolation sentinel test. The suite total increased from 48 to 57, not 105: focused/historical runs repeat subsets and are not additional unique tests.

Wider historical candidates were inspected but not executed: `tests/test_usd_direction_guard.py` imports application modules and pytest fixtures; `tests/test_r10_offline_startup.py` requires a different stage harness; `tests/d8_concurrency_runner.py` targets application/database startup; and R.86 snapshot provenance tests import SQLite/journal/startup code under their own isolation module. None has had its complete isolation and state-access closure verified for this task. They are **not run**, not passing, not unittest skips, and not classified as new product regressions. Existing known full-suite failures and the pre-existing seal mismatch are not fixed or hidden by these results. No historical hash expectation was changed.

## Changed files and SHA-256 integrity

Source manifests `SOURCE_INTEGRITY_BEFORE.json` and `SOURCE_INTEGRITY_AFTER.json` contain raw SHA-256 records for 232 selected source files: tracked Python under forex_bot/scripts/deploy, main.py, the new pure model, coordinator, runner, tests, preserved proposal and four historical gate source files. Exactly three source files differ, all offline:

- `offline_exposure/fake_coordinator.py`
  - before: `1b2bdf42dd0e001bb8735f2f486aded8b65eed99c56ac01e8b0e3fe62b23b7b9`
  - after: `08ecf35832cea2196d115cf151c0f42b3ca92fa1807c2cdb88047622bda9b2df`
- `offline_exposure/test_contract.py`
  - before: `d57a182ee84120d39b9348f64a46ebb5411ea3cb017fbd962d9166f7e9dc4888`
  - after: `6f1df8e850d3ea0b08ed771d40d1b7e9e29e52a6c318dc061135a9d54b0ce335`
- `offline_exposure/run_checks.py`
  - before: `89303fb48b99cacd7300f158911485895cbc18a0cdea25336d51c7e5866cc572`
  - after: `104bc60970b74a9a00dcba52b3715783d7b63b1dd7d358aec39c508c3f2ce04a`

Unchanged pure model: `ab7b446d7b1491832e311eaf594e4ba70a9e349becef72df88197cbbf6625405`.

Unchanged local bot_loop.py: `2f1c36dc025d114685e4424402f6866c66aa6eb37d28717027c502a4f447118d`. Required historical R.86 seal remains `a2310a7f2d2aee4b60c3c471cdd56ed48c72e2ed29232047c404209537e58d81`; the existing source-only archive still matches it in the unchanged historical regression. Local wrapper mismatch remains **unresolved**, not an integrity pass against that historical seal. No wrapper migration/restoration was attempted.

No operational source in the manifest changed. Four historical gate-source hashes are unchanged; read-only source checks show their confirmation receipts use network_permitted=False. The one-session permit is absent before and after. Consumed-marker existence is unchanged; its contents were not read, hashed or modified. Metadata is recorded in `PERMIT_METADATA_BEFORE.json` / `PERMIT_METADATA_AFTER.json`. No live process, credentials, gate-state store or production journal was inspected, so **effective runtime gate disablement is not independently verified**. No readiness claim follows from source or metadata checks.

New report artifacts are this document, source/permit manifests and six logs (two pre-fix, first post-fix, focused, complete, historical). Existing modified scheduler files and all other pre-existing work were left untouched. A PowerShell glob-style source search initially produced a filename-pattern error; it was rerun using rg's `-g` source filters. This inspection error did not execute application code.

## Remaining risks and final answers

- Can two concurrent calls successfully publish the same generation? **No in the tested in-memory contract**: the lock and consumed completion permit exactly one success; both ordered winners and a barrier-started race pass.
- Can an older generation overwrite a newer generation? **No in the tested schedules**: stale success/failure are inert, including while the newer refresh remains active.
- Can a failed refresh be revived by a late response? **No**: it remains failed until a newly issued generation completes successfully.
- Can refresh/reservation/dispatch interleavings release occupied capacity or create unsupported dispatch authority? **Not in the tested A–F schedules**. They preserve occupied slots and intents; refresh-first blocks admission/dispatch, and dispatch-first retains possible in-flight exposure. This is not proof over arbitrary evidence or every method interleaving.
- Are fixes confined offline with operational trading behaviour unchanged? **Yes**: only fake coordinator validation, synthetic tests and optional offline runner selectors changed; operational source hashes are unchanged. No integration path was added.

New-generation publication still trusts a caller's valid complete snapshot and can replace the occupied view. These tests do not authenticate terminal evidence, establish broker-event continuity, approve freshness, or prove arbitrary slot removal safe. Source mutation, mutable public fixture state, arbitrary exceptions from hostile objects, crash recovery, terminal lifecycle handling, all account writers and exhaustive interleaving/model checking remain outside the demonstrated guarantees. Threads sharing one RLock are not separate processes; independent fake instances still over-admit as the existing counterexample shows. No durable coordinator or broker-side idempotency is claimed.

The isolated changes have passing focused/full/original regression evidence and are ready for **review as an offline-only patch**. They are not ready for an unqualified merge/release to default main: the required seal, wider applicable historical isolation/checks, real broker evidence and effective gate verification remain unresolved or missing. No commit/push is authorised while those required checks remain missing; isolate any future reviewed commit scope explicitly. Stop at this report. **PRODUCTION TRADING REMAINS NO-GO.**

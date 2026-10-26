# R.67B Concurrency and persistence

Design only. Reconciliation and `run_bot` share the RAM dict `positions` (`positions.py` 8–9, `app.py` 630–633, `R66-16`). This document defines how a later implementation coordinates them. It does not add a lock to the running bot and does not replace the database. `REAL_NETWORK_EXECUTION_NOT_TESTED`. Production trading remains NO-GO.

## Linearisation point

The linearisation point for a local state transition is the commit of one durable row update for that observation or that `close_operation_id`.

The RAM dict is a cache. An HTTP response is evidence waiting to be committed. A log line is not a commit. `close_position` (`bot_loop.py` 1084) is not a commit of flat. Two tasks are ordered by which commit landed first, not by which task entered a Python function first.

A transition that does not commit has not happened. The next reader uses the last committed version.

## Why the current tables cannot hold the invariant

The existing schema stays. This design does not drop or rewrite it.

| Existing record | What it can store | Invariant it cannot meet |
| --- | --- | --- |
| `positions` RAM dict | One `Position` per symbol | Both sides, many trade ids, observation versus authority (`R66-16`). Lost on restart. |
| `reconcile_metadata` | One singleton run summary (`database.py` 48–57) | No per-side epoch, no snapshot hash. |
| `operational_event_log` | Append-only from/to text (`database.py` 60–67) | No identity key and no conditional update. |
| `exec_orders` | Open-order `client_order_id` unique (`database.py` 74–90) | Close lifecycle is not an open reservation. Mixing them would collide with the unreachable reserve-then-return tail (`bot_loop.py` 1623–1706, `R66-02`). |
| `broker_exit_ledger` | Closing transaction id plus trade id (`database.py` 96–103) | Evidence of a booked exit. Not a close-operation state and not an authority grant. |
| `broker_exit_pending` | Primary key `symbol` (`database.py` 106–114) | One row per symbol cannot represent a book side, a trade-id set, or one in-flight `close_operation_id`. |

`broker_exit.resolve_broker_exit` remains the read-only classifier for a disappeared trade (`broker_exit.py` 176–202). A later implementation may copy its transaction ids into the close operation. It must not use `broker_exit_pending`'s symbol key as the close identity.

## Additive records

These records are specified, not created. They sit beside the tables above.

Observation, one row per trade id:

- Identity fields from R.67A, including `book_side` and `broker_units`.
- `version` integer, incremented by the committed transition.
- `reconcile_epoch` and `snapshot_id`.
- Reconciliation state from the state machine.
- R.67A protection fields, stored separately from any local reference price.
- `pending_close_id` empty, or one `close_operation_id`.

Close operation, one row per attempt:

- `close_operation_id` unique.
- Account, instrument, book side, trade ids, granted units, endpoint name `PositionClose`, grant id, `snapshot_id`.
- Lifecycle state and its own `version`.
- Response evidence nullable: fill transaction id, per-trade closed units, or a reject transaction id.

Authority grant, history plus effectiveness:

- Grant id, scope `MONITOR` or one `CLOSE`, expiry, `revoked_at`, `consumed_at`.
- Effective execution authority is process-local. A committed grant row loaded at start is history. It is not permission to send (`R67A` invariant 10).

Single-flight is a uniqueness rule: at most one close operation for a given account, instrument, and book side may be in `CLOSE_SUBMITTING`, `CLOSE_OUTCOME_UNKNOWN`, `CLOSE_RECONCILIATION_REQUIRED`, or `CLOSE_MANUAL_REVIEW_REQUIRED`. A second insert fails and must not call the network.

## Coordination without a lock across I/O

`reconciliation_loop` and `run_bot` are separate tasks (`app.py` 158–170, 630–633). The design splits writers:

- Reconciliation commits observation fields and epochs only.
- The trading loop may commit a close-request note. It does not commit a grant.
- One authority writer commits grants. Import, reconcile, and the manage branch are not that writer.
- The close submitter is the only caller that may move `CLOSE_AUTHORISED` to `CLOSE_SUBMITTING`, and only inside the pre-send commit.

Network calls happen after the commit returns and before the next commit. No database lock and no in-process lock is held while waiting for OANDA. The process-wide `_pg_lock` in `database.py` is an existing connection lock. This design does not extend it across a broker call. A later implementation keeps any such lock inside the short transaction that reads version N and writes version N+1.

### Optimistic concurrency

An update carries `WHERE version = N`. Zero rows means another commit won. The loser re-reads.

| Loser was trying to | Required behaviour |
| --- | --- |
| Refresh an observation from a new snapshot | Re-read. If a `pending_close_id` appeared, apply the snapshot without clearing it. |
| Consume a `CLOSE` grant | Do not send. The other commit owns the attempt, or the grant is already consumed. |
| Mark flat | Do not retire if the committed state is an unresolved close or a conflict. |
| Attach protection | Write protection only if the trade id and snapshot still match. Otherwise leave the previous protection state. |

There is no retry of the HTTP call after a version conflict.

### Short critical section

The critical section is one transaction:

1. Read the observation version, the close-operation state, and the grant.
2. Reject the transition if the state or the snapshot does not match.
3. Write the new state and `version + 1`.
4. Commit.

Then, outside that section, perform the read or the single submit. Then a second short transaction records the evidence. If that second commit fails, the durable state is still the pre-send `CLOSE_SUBMITTING` or the last observation epoch. Recovery treats an uncommitted response as `CLOSE_OUTCOME_UNKNOWN`. It does not send again.

### Per-position versions

The observation version and the close-operation version are separate counters. A snapshot refresh must not bump the close operation into a sendable state. A close transition must not bump the observation into `MANAGEMENT_AUTHORISED`.

`local_tracking_id` is stable across versions. Trade ids may shrink only when a committed read says so. A version that drops a trade id without `PARTIAL_REDUCTION` or `BROKER_FLAT_CONFIRMED` evidence is an illegal transition.

### Broker snapshot timestamps and epochs

`snapshot_id` includes the completion time of a complete read. `BROKER_SNAPSHOT_FRESHNESS` and `PROTECTION_FRESHNESS` stay unnamed symbols. This document does not assign durations.

A failed read does not create a snapshot and does not increment `reconcile_epoch`. Management compares the grant's `snapshot_id` to the observation's current `snapshot_id` inside the short transaction. A mismatch drops `MANAGEMENT_AUTHORISED` back to `TRACKED_UNMANAGED` and invalidates an unconsumed `CLOSE` grant.

### Single-flight close submission

The pre-send transaction inserts or updates the operation to `CLOSE_SUBMITTING` under the uniqueness rule. The HTTP call is then allowed once in that process. A second task that loses the unique insert does not call `PositionClose`. A restart that finds `CLOSE_SUBMITTING` converts it to `CLOSE_OUTCOME_UNKNOWN` in a short transaction and does not call `PositionClose`.

### Atomic state transitions

Each legal edge in the close lifecycle is one update from an explicit prior state. An update that names the wrong prior state changes zero rows. There is no path that sets `CLOSE_FULLY_CONFIRMED` and clears the observation in two uncommitted steps. Flat confirmation of the observation is a later transaction that requires the close operation to already be classified and the read evidence to already be stored.

### Restart recovery

On process start, before `run_bot` manages anything:

1. Effective execution authority is empty.
2. Every `CLOSE_AUTHORISED` row that is not `CLOSE_SUBMITTING` is revoked.
3. Every `CLOSE_SUBMITTING` row becomes `CLOSE_OUTCOME_UNKNOWN`.
4. `MONITOR` grants are not effective until a complete snapshot in this process matches them.
5. Protection loads as `PROTECTION_STALE` when a verification record exists, otherwise `PROTECTION_UNKNOWN`. A price without a stop order id loads as `LOCAL_REFERENCE_ONLY` or `PROTECTION_UNKNOWN`, never `BROKER_PROTECTED`.
6. RAM `positions` may be filled only as a cache of observation rows. Loading it must not set `execution_kind` into authority. Today's startup loads orders, not positions (`app.py` 574–579). Adding a position load later is still observation-only.

`initialise_fail_closed` already ignores a stored open-allowed flag (`live_safety.py` 401–402) and then exempts closes (`102–106`). Recovery in this design closes that exemption for bot-originated closes. It does not take the account away from a human.

## Protection alongside concurrency

Protection writes use the same optimistic rule. A reconcile task and a manage task must not both own `confirmed_broker_stop_price`. Only a committed trade-read transition may set it, and only together with `broker_stop_order_id` and `broker_stop_verified_at`.

The scenario outcomes are in the reconciliation document. Concurrency adds these ordering constraints:

| Scenario | Who may commit | Who must not |
| --- | --- | --- |
| Broker stop present | The task that finished `TradeDetails`, if the version matches | The manage loop, using `stop_loss` |
| Broker stop missing | The same trade read, setting `UNPROTECTED_CONFIRMED` | Any task sending a stop |
| Local fallback present | Observation may store `local_stop_reference` | Any task copying it into the confirmed field (`R66-05`) |
| Stop cancelled manually | The next committed trade read | A stale `BROKER_PROTECTED` row left in place |
| Snapshot stale | The epoch task, setting `BROKER_STATE_STALE` and `PROTECTION_STALE` or `PROTECTION_UNKNOWN` | A close submitter using the old snapshot |
| Amendment rejected | No bot task. The bot does not amend. | A retry of an amendment that was never authorised |
| Partial reduction | The close-evidence transaction, then a read transaction for the remainder | A task that deletes the parent because the fill units were short (`R66-10`) |
| Fully closed | Flat transaction after evidence is committed | `close_position` racing ahead of that commit |
| Restart, protection missing | Recovery transaction that sets unknown or stale | A startup task that attaches a stop |

No automatic stop attachment or amendment is part of this design. A protective order would need a grant this contract does not define (`R67A`).

## Database unavailable

If the commit cannot start, the transition does not happen and the HTTP call does not start. If the database fails after `CLOSE_SUBMITTING` is committed and before the response commit, recovery is `CLOSE_OUTCOME_UNKNOWN` once the database is readable. While it is unreadable, no new close starts, no observation is retired, and the RAM cache must not be treated as the book of record. `log_only` continues to mean observation only when reads and commits are possible. It does not gain authority because the database is down.

## Shared-book rule for the current dict

Until those records exist, the RAM dict cannot represent the split. The design rule for a later change is: reconciliation replaces observation cache fields under a version check; it does not write grant fields; the manage loop does not call `PositionClose` unless the pre-send row committed in this process. This stage does not implement that change. The current unlocked dict remains the `R66-16` defect.

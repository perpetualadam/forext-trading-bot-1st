# Source change log

## forex_bot/database.py

Defect: the reservation transaction blocked only UNRESOLVED, then committed PENDING and dropped the lock.

Path: `insert_exec_order_pending_if_absent`.

Invariant: a committed or in-process PENDING, PARTIAL, UNRESOLVED, or unknown status blocks another client id for that symbol.

Change: one blocking policy; process blocking map; select of non-terminal statuses inside the same try as the insert; rollback when a blocking row is found; fail-closed on a reservation fault. Recovery read now includes PENDING and PARTIAL as well as UNRESOLVED. A full fill or authoritative cancel releases the reservation hold only. `order_status_proves_exposure_closed` is always false.

Regression: `tests/test_r8_reservation_safety.py`. Failure mode and the existing R.4, R.5, and R.7 suites were rerun. Protected hashes were rechecked.

Limitation: PostgreSQL did not execute this SQL.

## forex_bot/orders.py

Defect: `try_begin_order_submission` could accept a second id while a PENDING or PARTIAL order was already in memory, and recovery restored a block only for UNRESOLVED.

Change: memory status check before insert; recovery notes PENDING, PARTIAL, and UNRESOLVED; cancel releases the hold except for UNRESOLVED; a full fill releases the reservation hold and does not create a position.

`bot_loop.py` was not modified. It already calls these functions before broker dispatch.

## tests/test_r5_integration.py

One assertion changed from true to false in `test_h28_legacy_pending_and_partial_rows_keep_their_status`. The status and direction assertions are unchanged. The old true result was the pending-window hole.

## Not modified

`forex_bot/bot_loop.py` hash remains `b16bb86a9cd30306a0200c0fab9f105ceeb78f82903ebebd4b3082eea77291c7`.

No strategy, sizing, risk, live-auth, broker host, startup, or migration change.

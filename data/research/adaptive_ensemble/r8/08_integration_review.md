# Integration with existing safety

`_evaluate_impl` still calls `broker_entry_block_reason` and then `try_begin_order_submission` before `execute_oanda_market_open`. That order is source-reviewed at bot_loop.py 1554–1639. The loop was not started. `bot_loop.py` was not edited; its hash matches the R.8 baseline.

A database or in-memory refusal returns false from `try_begin_order_submission` and does not register the new order. The false result is not treated as a successful reservation. The in-memory check cannot override a later database refusal because a false insert returns before `register_order`.

Preserved behaviour, rerun under the R.8 barrier:

- Invalid direction returns before sizing.
- An inactive strategy returns before sizing.
- Live-order authorisation remains blocked on a synthetic state file that says ALLOWED.
- UNRESOLVED is kept, and `mark_order_failed_or_cancelled` does not change it.
- Recovery failures block a new entry.
- Confirmed cancel, reject, and fill helpers do not create a replacement id.
- No test called the broker.

`tests/test_r5_integration.py` `test_h28_legacy_pending_and_partial_rows_keep_their_status` previously expected a new client id to be accepted while PENDING and PARTIAL rows were loaded. That expectation was the defect. The status checks remain. The new-id assertion is now false. This is a tighter safety assertion.

`test_h39_h40_restart_keeps_live_orders_blocked` was deselected for this run so the existing R.5 fixture file was not rewritten. The same live-auth invariant was executed by `test_i33_live_authorisation_stays_blocked` against a file under r8.

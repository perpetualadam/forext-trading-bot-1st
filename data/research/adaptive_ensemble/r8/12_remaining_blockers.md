# Remaining blockers

The pending-window hole in the reservation function is repaired in source and covered by synthetic tests. It is not engine-proven.

1. PostgreSQL concurrency and persistence are NOT_EVALUATED. The check-and-insert text was read. It was not executed. No atomicity or lock-visibility claim is made.
2. FILLED does not prove an open position is closed. The reservation hold is released on a full fill so the symbol is not permanently blocked. The loop's position object still stops a new entry while that object exists. A fill that never records a position can reach a later reservation. That needs a separate position-state design. No migration was added.
3. `exec_orders` still has no unique open-row constraint per symbol. Rows written outside `insert_exec_order_pending_if_absent` can duplicate. Recovery of several active rows blocks a new id. A constraint would be a migration and was not added.
4. `test_h39_h40_restart_keeps_live_orders_blocked` was not executed in this run. `test_i33_live_authorisation_stays_blocked` covered the same effective-auth result on an r8 file.

No repair was stopped for an out-of-scope file. The position-state gap was stopped because a correct fix is broader than the reservation policy.

# Pending-window repair

Defect: `insert_exec_order_pending_if_absent` took `pg_advisory_xact_lock`, selected only `status = UNRESOLVED`, inserted PENDING, and committed. The lock ended at commit. A second client id could reserve the same symbol before the first order became UNRESOLVED. An exception returned false without fail-closing, so a later id could proceed after an uncertain commit.

Invariant: after the first reservation is accepted, another client id for that symbol is refused while the first order is PENDING, PARTIAL, UNRESOLVED, or has an unknown status.

Repair, in `forex_bot/database.py` lines 762–840:

- The process lock checks the fail-closed flag, the unresolved map, and the blocking map before any insert.
- With persistence off, the blocking map is set before the function returns true, so a second thread sees the first hold.
- With persistence on, the source takes the advisory lock, selects any row for the symbol whose status is not FILLED, CANCELLED, or REJECTED, and inserts only when that select is empty. The check and insert are in one try, with one commit.
- A found row is rolled back so the transaction lock is not left open. That rollback was not executed against PostgreSQL.
- A commit exception records the symbol hold, sets the process fail-closed flag, and returns false. There is no retry.

`try_begin_order_submission` also refuses when the in-memory book already has a blocking status for the symbol. A false return does not register an order and does not reach broker dispatch in the loop source.

Evidence: CODE MODIFIED and SYNTHETICALLY TESTED. POSTGRESQL-ENGINE TESTED: no. The advisory lock still ends when the transaction ends. The source relies on the committed row being visible to the next check. That visibility was not engine-tested.

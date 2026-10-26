# Concurrency lock review

SOURCE-REVIEWED. The lock was not executed.

`insert_exec_order_pending_if_absent` takes `pg_advisory_xact_lock` inside the same transaction as the unresolved check and the insert (`database.py` around lines 711–740). The lock ends when that transaction commits or rolls back.

What the source shows:

- The lock is held for the check and the insert. A second session cannot pass that check until the first transaction ends.
- The check looks only for status `UNRESOLVED`.
- The insert commits the row as `PENDING` and releases the lock before the broker call and before the row can become `UNRESOLVED`.
- After that commit, a second client id for the same symbol is not blocked by this check, because the first row is still `PENDING`.
- There is no unique constraint that would stop that second insert.
- The lock key is a CRC32 of the symbol text. The same uppercased symbol always gets the same key. Two different symbols can theoretically share a key. That would make them wait on each other. It would not open a hole by itself.
- The key function does not uppercase. The insert path uppercases the symbol before it calls the function.
- A database exception returns False and rolls back. That is fail-closed for the caller that saw the exception.
- If the server committed and the connection then failed before the client saw success, the caller still gets False, but a `PENDING` row may exist. That row does not block a different client id.
- Lock timeout and deadlock behaviour were not executed. The exception path returns False, which is fail-closed only if the server raises into that path.

This is not concurrency safety. It is the reason the engine tests were required and were not run.

No source change was made. A repair of the pending-window hole needs an engine test before it is trusted, and this stage could not start PostgreSQL safely.

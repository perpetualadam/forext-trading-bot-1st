# D.9 lock design

`_pg_lock` remains a `threading.RLock`. No second lock was added.

`get_connection` now acquires that lock before the reuse check and holds it until the function returns. The critical section is:

1. If `_pg_conn` exists and is not closed, return it.
2. Otherwise connect, create the cursor, run the existing initialization SQL, and commit.
3. Assign `_pg_conn` and `_pg_cursor` before releasing the lock.
4. On failure, discard only the local objects and return `None`. The globals are not assigned and are not cleared.

A second caller blocks on the lock. When it enters, it rechecks the globals. After a successful first caller, it reuses that connection and does not call `psycopg2.connect`.

Helpers already wrap `get_connection` in `with _pg_lock`. The reentrant lock lets that nested call through. A second thread's helper waits instead of connecting.

Release still copies and clears the globals under the lock, then closes outside it. It does not call `get_connection`. There is no lock-order cycle: the only lock is `_pg_lock`.

The two assignments are inside the lock. Production readers of `_pg_conn` and `_pg_cursor` are the helpers and the release helper, and both hold the lock while they read. No production module outside `database.py` reads those globals. Pair publication is safe for callers that follow this lock. An unlocked reader added later could still observe the two assignments separately. That would be a new caller, not a current one. Fixing it does not require a change outside `database.py`.

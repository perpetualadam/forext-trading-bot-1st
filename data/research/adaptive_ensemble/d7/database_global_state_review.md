# D.7 database global-state review

Globals are `_pg_conn`, `_pg_cursor`, and `_pg_lock` (`threading.RLock`). There is no separate initialization flag. `_partial_cleanup_notes` records cleanup type names for the latest failed attempt.

Failed initialization does not assign the new objects to the globals. A later `get_connection` calls `psycopg2.connect` again. The isolated retry scenario observed two connect calls, a closed failed object, and a different open published object.

An already open global connection returns immediately. The isolated healthy-connection scenario observed zero connect calls and zero close calls on that object while cursor creation was set to fail.

Globals are cleared by `release_connection_after_failed_startup` only while they still refer to the objects copied under `_pg_lock`. The close happens on those copied objects after the globals are cleared, so a newer replacement is not closed.

Limitation: `get_connection` still does not hold `_pg_lock` across connect and schema statements. Callers of the cursor are documented to hold the lock, and the database helpers do. `lifespan` calls `get_connection` without the lock, as it did before. Two overlapping first-time initializations can still race. This stage did not add a cross-module lock or change those callers.

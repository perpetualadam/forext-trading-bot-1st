# D.9 ownership review

The module still owns the published connection and cursor. `get_connection` returns the connection object. Production lifespan ignores that return. Helpers use `_pg_cursor` inside `_pg_lock` and return rows or status values, not the connection.

A failed attempt owns its local connection and cursor only. `_discard_partial_connection` closes those objects and does not publish them. A later success publishes a new pair. The post-fix failure schedules created a second connection only after the first attempt had failed and released the lock. That second connection was the one published. The failed object was closed by the application when close succeeded.

Holding a Python reference after `get_connection` returns is continued reachability. It is not, by itself, proof that code is executing a query. The release helper closes the object it copied. The direct-call release test observed that close. Production lifespan does not keep the returned object.

Successful startup still leaves the published connection open for the process lifetime. D.9 did not change that rule and did not change `app.py`.

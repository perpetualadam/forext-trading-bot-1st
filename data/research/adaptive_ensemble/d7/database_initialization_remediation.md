# D.7 database initialization remediation

`get_connection` still returns `None` when PostgreSQL initialization fails, and it still logs `PostgreSQL unavailable`. That public contract is unchanged.

The new connection and cursor are local until `commit` succeeds. Only then are they stored in `_pg_conn` and `_pg_cursor`. A failure therefore cannot publish a half-initialized connection.

On failure after `connect`:

1. The original exception is logged with the existing warning.
2. The cursor is closed once, if it exists and is not already closed.
3. The new connection is rolled back if it is still open.
4. The new connection is closed if it is still open.
5. A cleanup exception is recorded by type name and does not replace the `None` return.
6. Globals are left unchanged, so a different healthy connection is not closed and a failed object is not reused.

`CREATE` and `ALTER` statement text was not modified. `git diff` of `database.py` contains no added or removed `CREATE` or `ALTER` lines.

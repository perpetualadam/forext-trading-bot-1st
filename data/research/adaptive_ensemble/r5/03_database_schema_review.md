# Database schema review

SOURCE-REVIEWED. PostgreSQL was not started and no SQL statement was sent to an engine.

`exec_orders.status` is `TEXT NOT NULL`. There is no check constraint limiting the status words. The value `UNRESOLVED` therefore fits the existing table without a new column.

The recovery query now selects `PENDING`, `PARTIAL`, and `UNRESOLVED`. A cancelled update no longer rewrites a row whose status is already `UNRESOLVED`.

Reservation takes `pg_advisory_xact_lock` and then looks for an unresolved row for that symbol before insert. If the connection, the lock, or the insert fails, the function returns False. That pattern was not executed against PostgreSQL.

`fetch_exec_orders_open_for_recovery` used to return an empty list when the connection or the query failed. It now raises `OrderRecoveryUnreadable`. The loader catches that and sets the process fail-closed flag. An empty result is no longer used as proof that no unresolved order exists.

No production migration was run. No new table or column is required for the status word. The advisory lock uses a built-in PostgreSQL function and does not add an index.

Status: `POSTGRESQL_EXECUTION_NOT_EVALUATED`.

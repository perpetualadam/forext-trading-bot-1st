# R.77 schema and migration

`SCHEMA_VERSION` is 4. `open_journal` refuses every other version with `unsupported_schema`. Startup, `active_journal`, and `run_bot` do not migrate.

## Schema 4 additions

- Permanent unique index `one_client_order_id`.
- `client_order_id_registry`.
- `recovery_repairs` (lines 159–176), an append-only audit table. It has no unique index on `target_run_id`, so a recorded refusal does not block a later successful repair of the same run.
- The R.76 partial index `one_unresolved_entry` is not created for a new journal.

Existing close, managed-position, and recovery-run tables stay. WAL and `synchronous=FULL` are still applied by `_configure` (lines 715–724).

## Version detection

`schema_meta.schema_version` is read by `open_journal` (line 800). Version 3 and version 2 both fail closed. Test 28 set a live schema-4 file back to version 3 and `open_journal` refused it.

## Explicit migration

`migrate_journal_3_to_4` (`forex_bot/close_journal.py` lines 878–976) opens the path with `sqlite3` directly. It does not call `open_journal`.

Prerequisites and order:

1. The file exists, is non-empty, and `PRAGMA integrity_check` is `ok`.
2. `schema_version` is exactly 3. Any other version raises `schema_migration_refused` before DDL.
3. Duplicate `(account_binding, client_order_id)` groups raise `historical_client_id_conflict` before DDL. Rows are not deleted or rewritten.
4. `BEGIN IMMEDIATE` drops `one_unresolved_entry`, creates the permanent index and the two new tables, copies entry ids into the registry, and sets version 4.
5. `fail_before_commit=True` rolls back and raises `migration_interrupted`. The file stays version 3.

`create_legacy_schema_3_database` (lines 845–875) writes a synthetic version-3 file for tests and refuses an existing path. It is not used by startup.

Rollback of a committed migration is not automatic. A committed version-4 file is not rewritten back to version 3 by this stage. An interrupted migration leaves version 3, which startup continues to reject.

Tests 41, 42, and `test_successful_migration_installs_permanent_uniqueness` covered duplicates, interruption, and a clean copy. Corrupt input is refused by `open_journal` and by the migrator.

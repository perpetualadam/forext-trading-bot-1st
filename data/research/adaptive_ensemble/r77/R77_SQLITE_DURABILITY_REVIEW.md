# R.77 SQLite durability review

`_configure` still sets `journal_mode=WAL` and `synchronous=FULL`, and it refuses any other result (`close_journal.py` lines 715–724). Connections use `isolation_level=None`, so every commit is an explicit `COMMIT`. Writers take `BEGIN IMMEDIATE`. The busy timeout remains `CLOSE_JOURNAL_BUSY_MS`.

Transaction boundaries added in this stage:

- Entry reservation plus registry insert, then a second transaction that moves intent 0 to intent 1.
- `commit_verified_entry`: position insert and `ENTRY_FINALISED` update, one commit.
- Repair: claim update and audit insert, one commit.
- Migration: DDL, registry copy, and version update, one commit, and only when the operator calls the migrator.

The permanent unique index and the registry primary key are the client-id constraints. `one_managed_trade` remains the trade-id constraint. `one_recovery_in_progress` remains the single-flight recovery claim.

Crash classes:

- A Python exception inside `commit_verified_entry` or `_record` calls `_rollback`. Tests 03 and 61 used the existing `before_commit` fault, which rolls back before `COMMIT`.
- Process restart was simulated with `reset_journal_process_state` and a new `open_journal`. Committed finalisations and committed repairs were still present. Rolled-back finalisations were not.
- An operating-system crash and a power loss were not performed. WAL plus `synchronous=FULL` is the configured durability mode. It is not evidence that a power loss cannot tear a frame on this Windows or OneDrive-backed filesystem. `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED` stays.

Journals used by tests were temporary files. The operational journal path was not opened. A missing configured path raises `missing_journal` and does not create a file. Uniqueness does not survive deletion of the journal file.

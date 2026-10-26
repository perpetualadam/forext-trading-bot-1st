# R.75 SQLite Durability Review

`_configure` (`close_journal.py` lines 647–656) still sets:

- `PRAGMA journal_mode=WAL`, and refuses any other mode
- `PRAGMA synchronous=FULL`, and refuses a value below 2
- `PRAGMA busy_timeout` from `CLOSE_JOURNAL_BUSY_MS` (default 5000 ms; tests use 300 ms)

Connections use `isolation_level=None` and explicit `BEGIN IMMEDIATE` / `COMMIT`. Schema version is 2. `PRAGMA integrity_check` must return `ok` or the file is `corrupt_journal`.

Unique unresolved closes remain `one_unresolved_close` on `(account_binding, instrument, trade_id)` where confirmation is not `CLOSE_REJECTED_CONFIRMED` or `CLOSE_FINALISED`. Owner tokens are random hex stored on the row. A claim compares the token inside the update. There is no lease expiry that hands the token to another process.

`network_permit` starts at 0 on reserve and on preexisting blockers. Only `claim_network_permit` sets it to 1, in the same immediate transaction as `submission_state='SENT'`.

## Filesystem

Tests use `tempfile.TemporaryDirectory`, not the OneDrive working tree, for the journal and the recorder. The operational path reads `CLOSE_JOURNAL_PATH`. This stage does not create an operational journal under OneDrive or Dropbox. Placing that file in a synchronised directory is still unsupported: locking and durability semantics of those filesystems were not verified.

## What was not weakened

WAL and `synchronous=FULL` were not reduced to make tests pass. A v1 file is not migrated. It fails as `unsupported_schema`.

## Power loss

`SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED`. See the crash-window note. Killing a process is not a power-loss test.

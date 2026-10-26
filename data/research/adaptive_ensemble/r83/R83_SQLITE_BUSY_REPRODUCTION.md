# R.83 SQLITE_BUSY reproduction

## Production WAL

`open_journal` forces `journal_mode=WAL` and refuses any other mode (`close_journal.py` `_configure`). R.82 showed that `BEGIN EXCLUSIVE` on a second connection left the open WAL reader able to read `recovery_authority`. This stage did not change that mode and did not make the production SELECT raise `SQLITE_BUSY`.

`SQLITE_BUSY_AUTHORITY_READ_NOT_REPRODUCED` for the production WAL path.

## Disposable DELETE-mode database — genuine driver error

`test_09_rollback_select_raises_sqlite_busy` uses a separate file, not the trading journal.

| Item | Value |
| --- | --- |
| Journal mode | `DELETE` |
| Holder | `BEGIN EXCLUSIVE` |
| Reader timeout | 0 |
| SQL | `SELECT fencing_epoch FROM recovery_authority WHERE id = 1` |
| Exception | `sqlite3.OperationalError` |
| `sqlite_errorname` | `SQLITE_BUSY` |
| `sqlite_errorcode` | 5 |
| Broker writes | 0 |

This proves the installed SQLite driver raises `SQLITE_BUSY` for that SELECT when the database is in rollback-journal mode. It does not prove the WAL production path does the same. The production journal mode was not changed.

## Injected error

`test_11` raises `sqlite3.OperationalError("database is locked")` from the third `live_management_permitted()` call, which is the post-slot check, once for OrderCreate and once for a separate GBP_USD PositionClose. Label: `INJECTED_SQLITE_BUSY`. Both request counts stay 0. That injection is not a SQLite lock.

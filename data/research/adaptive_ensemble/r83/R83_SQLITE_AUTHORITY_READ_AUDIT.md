# R.83 SQLite authority-read audit

`_authority_matches` in `startup_recovery.py` 140-148 selects `fencing_epoch` from `recovery_authority`. It catches only `JournalUnavailable` and then returns false. `sqlite3.OperationalError` and `sqlite3.ProgrammingError` propagate.

`live_management_permitted` calls that function after checking that recovery is complete and the process epoch exists. A missing row or a different epoch returns false. The OrderCreate and PositionClose sinks call this before `api.request`. A false result raises `EntryGuardRefusal` or `CloseGuardRefusal`. A propagating SQLite error is still before `api.request`. On the entry sink it is classified as a transport outcome. On the close sink `run_guarded_live_close` records an unresolved close. Neither path sends the request.

| Condition | Caught as false | Propagates | Request |
| --- | --- | --- | --- |
| `JournalUnavailable` | Yes | No | Not sent |
| Missing authority row | Yes, because the SELECT returns no row | No | Not sent |
| Stale epoch | Yes | No | Not sent |
| Closed connection `ProgrammingError` | No | Yes | Not sent |
| `OperationalError` such as busy or locked | No | Yes | Not sent if it happens on this SELECT |
| Readable WAL during another connection's exclusive transaction | The SELECT succeeds | No | The check can still pass |
| Readable journal that cannot commit | The SELECT succeeds | The later commit fails | The request can already have been sent |

A propagated exception is fail-closed for the broker call. It is not the same as a successful authorisation.

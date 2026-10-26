# R.83 SQLITE_LOCKED reproduction

The production journal does not enable SQLite shared cache. A shared-cache fixture is not the production configuration.

`test_10_shared_cache_begin_raises_sqlite_locked`:

| Operation | Result |
| --- | --- |
| URI | `file:r83lock?mode=memory&cache=shared` |
| Holder | `BEGIN IMMEDIATE` after inserting the authority row |
| Other connection SELECT of `fencing_epoch` | Succeeds. No error |
| Other connection `BEGIN IMMEDIATE` | `sqlite3.OperationalError` |
| `sqlite_errorname` | `SQLITE_LOCKED_SHAREDCACHE` |
| `sqlite_errorcode` | 262 |
| Broker writes | 0 |

The authority SELECT itself did not raise `SQLITE_LOCKED`. The locked error was on a later write transaction in a shared-cache database. That is not relabelled as a failure of the production authority read.

`SQLITE_LOCKED` at the production WAL authority SELECT was not reproduced.

`test_11` also injects `sqlite3.OperationalError("database table is locked")` on the entry sink and on the EUR_USD close sink. Label: `INJECTED_SQLITE_LOCKED`. OrderCreate and PositionClose counts stay 0. Each close stays short of `CLOSE_FULLY_CONFIRMED`, and the permit row is consumed because the claim happened before the injected check.

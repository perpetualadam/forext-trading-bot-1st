# Source change log

Modified:

- `forex_bot/bot_loop.py` — strategy gate is a function the loop calls; unresolved outcomes update the in-memory order to `UNRESOLVED`; unknown strategy names no longer index the strategy map.
- `forex_bot/database.py` — recovery failure raises; unresolved intent can be restored; cancel cannot overwrite `UNRESOLVED`; reservation checks the process map under the lock and takes a transaction advisory lock before insert.
- `forex_bot/orders.py` — `UNRESOLVED` status, snapshot ingest, and a cancel guard.

Not modified: `oanda_exec.py`, `app.py`, `live_safety.py`, `strategy_meta.py`, `trading.py`, `config.py`, deployment files.

`backtest.py` still has the old direction fallback. It is not on the application startup path and it was outside the approved edit list.

Git diff versus HEAD for the three edited application files: 614 insertions, 95 deletions. Part of the database diff was already present before R.4. No commit was made.

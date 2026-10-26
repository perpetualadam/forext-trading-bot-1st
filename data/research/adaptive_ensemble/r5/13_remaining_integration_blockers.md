# Remaining integration blockers

1. PostgreSQL was not executed. Schema compatibility is source review only. The advisory lock, the unresolved update, and the recovery query are not engine-proven.

2. The application lifespan and `run_bot` were not started. The wiring is source-reviewed and the gates those functions call were tested directly.

3. `forex_bot/backtest.py` still turns a missing direction into BUY. It is not called by application startup. Changing it needs a separate approval because it is outside the R.5 edit list.

4. If recovery cannot be read, the process still starts, because `app.py` ignores a failed connection and was not edited. New broker reservations are then blocked by the fail-closed flag. That is not the same as refusing to boot.

5. No broker, practice, or live order was sent. Strategies were not enabled. Live permission was not granted.

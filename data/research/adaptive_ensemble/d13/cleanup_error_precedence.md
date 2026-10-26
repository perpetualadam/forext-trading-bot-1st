# Cleanup error precedence

The primary startup exception is stored and re-raised before cleanup. An incomplete Telegram stop adds a diagnostic string and does not become that exception.

A stop exception is still recorded as its type name and still sets `telegram_stop_failed`. Task cancellation and awaiting still run afterward. A task-await exception is still appended and does not skip later tasks.

On a successful startup, the first secondary exception is still re-raised when the current task is not cancelling. `D12-STOP-01` is a string in the cleanup list, so it does not take that path.

Database release still runs only when startup failed and the Telegram stop itself did not raise. An incomplete stop leaves that condition unchanged.

Isolated results: broker failure escapes as `RuntimeError` and releases the connection; a raising stop records `RuntimeError` and keeps the connection; `await_health` records `RuntimeError` with pending tasks at 0; a blocked stop records `D12-STOP-01` and does not escape.

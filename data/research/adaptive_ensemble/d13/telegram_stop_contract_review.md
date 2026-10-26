# Telegram stop contract

`stop_telegram_control` at `forex_bot/telegram_control.py` lines 1201–1225 returns a string.

Constants at lines 126–128:

- `STOP_COMPLETED`
- `STOP_INCOMPLETE_WORKER_ALIVE`
- `STOP_NOT_RUNNING`

The implementation returns `STOP_NOT_RUNNING` when no thread is stored. It returns `STOP_INCOMPLETE_WORKER_ALIVE` when the caller is the worker, or when `join(timeout=2.0)` leaves the worker alive. A dead worker is cleared only when `_poller_thread` still refers to that thread, and the function then returns `STOP_COMPLETED`.

The production function returns one of those three strings. It does not return `None` and it does not raise for a timed-out join. The stop event stays set.

`STOP_COMPLETED` and `STOP_NOT_RUNNING` are normal outcomes. `STOP_INCOMPLETE_WORKER_ALIVE` means the tracked worker is still alive. An unexpected value is possible only from a substitute, and `app.py` records it as `D12-STOP-UNKNOWN` without treating it as completion.

A historical stub that returns `None` supplies no documented status. `app.py` leaves that path silent so existing doubles keep an empty cleanup list. That silence is an absent status, not a claim of `STOP_COMPLETED`.

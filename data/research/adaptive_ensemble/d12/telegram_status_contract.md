# Telegram stop status contract

`STOP_COMPLETED`, `STOP_INCOMPLETE_WORKER_ALIVE`, and `STOP_NOT_RUNNING` are string constants at `telegram_control.py` lines 126-128.

`stop_telegram_control` (lines 1201-1225) sets the stop event, joins for at most 2.0 seconds, and returns one of those strings. A live worker stays in `_poller_thread`. A finished worker is cleared only if the stored reference is still that thread. No stored worker returns `STOP_NOT_RUNNING`. Timeout does not raise. The function does not log the status.

A later start can run after the worker exits. A start while the worker is alive does not clear the event.

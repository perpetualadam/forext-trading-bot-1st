# Telegram lifecycle contract

Constants at `telegram_control.py` lines 126–133:

- `START_STARTED`
- `START_ALREADY_RUNNING`
- `START_REFUSED_PREVIOUS_WORKER`
- `START_DISABLED`
- `START_FAILED`
- `STOP_COMPLETED`
- `STOP_INCOMPLETE_WORKER_ALIVE`
- `STOP_NOT_RUNNING`

`commands_enabled()` is line 169. A disabled or unconfigured command path returns `START_DISABLED` and creates no worker.

Under `_poller_lock`, start reaps a dead thread. An alive thread with the stop event set returns `START_REFUSED_PREVIOUS_WORKER` without clearing the event or starting another worker. An alive thread with the event clear returns `START_ALREADY_RUNNING`. Otherwise the event is cleared, the thread is stored, and `Thread.start()` runs. An `Exception` clears the reference and returns `START_FAILED`. `KeyboardInterrupt` is a `BaseException` and still propagates.

`stop_telegram_control()` sets the event under the lock, copies the thread reference, and joins for 2.0 seconds outside the lock. A live thread stays stored and the result is `STOP_INCOMPLETE_WORKER_ALIVE`. A finished thread is forgotten and the result is `STOP_COMPLETED`. No thread returns `STOP_NOT_RUNNING`.

The polling loop is `_poller_loop_inner`, lines 1114–1174. A poll exception breaks when the stop event is set. `_read_trades_if_running`, lines 602–614, holds `_pg_lock` and returns before the trade query when stop is set.

Result generation and worker ownership use the same lock. The result is not cached in a global. `reset_telegram_control_for_tests` clears the stop event only after the worker is no longer alive.

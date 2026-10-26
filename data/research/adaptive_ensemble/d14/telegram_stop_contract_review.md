# Telegram stop contract

`stop_telegram_control` was not modified.

It still returns `STOP_COMPLETED`, `STOP_INCOMPLETE_WORKER_ALIVE`, or `STOP_NOT_RUNNING`. The join timeout remains 2.0 seconds. A live worker stays in `_poller_thread`. The stop event is set under `_poller_lock` and is not cleared by stop. The lock is released before the join.

A later start sees that event while it holds the same lock. Refusal returns without clearing it. A dead worker can still be replaced, and that replacement is the only path that clears the event.

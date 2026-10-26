# Startup result concurrency

The result is chosen while `_poller_lock` is held, in the same section that already decided whether a worker exists.

`stop_telegram_control` sets the event under that lock and joins outside it. A start that acquires the lock during the join sees the event and the live worker, returns `START_REFUSED_PREVIOUS_WORKER`, and does not clear the event.

Two overlapping starts are serialized by the lock. One returns `START_STARTED`. The other sees the live worker and returns `START_ALREADY_RUNNING` when stop has not been requested. Isolated tests observed one worker and those two results.

No additional lock cycle was added. The start path does not join. A successful result is returned only after `Thread.start()` returns.

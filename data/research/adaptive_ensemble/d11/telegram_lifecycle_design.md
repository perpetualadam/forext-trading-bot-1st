# D.11 Telegram lifecycle design

`stop_telegram_control` sets the shared stop event under `_poller_lock`, copies the stored thread, and releases the lock before `join(timeout=2.0)`. After the join it checks `is_alive()`. A live worker stays stored and the return is `STOP_INCOMPLETE_WORKER_ALIVE`. A thread that has exited is cleared only when the stored reference is still that thread, and the return is `STOP_COMPLETED`. No stored thread returns `STOP_NOT_RUNNING`.

`start_telegram_control` reaps a dead reference. If the stored thread is alive it returns without clearing the stop event and without creating another thread. The thread object is stored before `Thread.start()`.

The worker clears the stored reference in a `finally` only when that reference is still itself. An old worker cannot erase a newer worker.

The join timeout remains 2.0 seconds. Stop does not raise because the join timed out. `app.py` ignores the return value, so the worker gate, not the return value, prevents new trade reads.

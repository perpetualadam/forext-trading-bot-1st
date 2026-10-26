# D.11 thread ownership

OWN-01 through OWN-09: a live worker remains in `_poller_thread`. Timeout does not clear it. A completed worker is cleared by stop or by its own `finally`. A later stop still sees a surviving worker. Start refuses a second worker and does not clear the event the survivor needs. After the survivor exits, start reaps the dead reference and may start one new worker.

OWN-10: the reference is assigned before `start()`, while `_poller_lock` is held.

OWN-11: stop clears the reference only when it is still the thread that was joined.

OWN-12: `_poller_lock` is not held across `getUpdates` or `join`. Stop does not acquire `_pg_lock`. The database gate acquires `_pg_lock` and the trade helper re-enters that same reentrant lock. There is no lock cycle.

If stop runs on the stored worker thread, it does not join itself. It returns `STOP_INCOMPLETE_WORKER_ALIVE`. Production command handlers do not call stop. The branch was exercised by storing a test thread and calling the real stop function.

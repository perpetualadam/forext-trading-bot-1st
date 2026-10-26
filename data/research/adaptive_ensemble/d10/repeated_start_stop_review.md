# Repeated start and stop

`start_telegram_control` prevents a second thread only while `_poller_started` is true. It does not call `is_alive()`.

Observed:

- Stop before any start returns immediately and creates no thread.
- A second stop after the worker has exited returns immediately. `_poller_thread` is already `None`.
- A second start while the first worker is alive and `_poller_started` is true does not create a second thread. One `telegram-control` thread was present (ident 14696).
- Stop during a blocked fake `getUpdates` returned in 2.006s with thread 13880 still alive, `_poller_started` false, and `_poller_thread` already `None`.
- The following `start_telegram_control` cleared `_stop_event` and started thread 17184. Both 13880 and 17184 were alive. This is overlapping workers.
- The old worker can then continue past the loop condition because the event was cleared. Both threads share the module-level poll configuration, offset, and `get_updates` lock. The HTTP call itself is serialized by `_GETUPDATES_LOCK`, but two workers exist.

The current `lifespan` calls start once and stop once. It does not itself perform this restart. The functions permit it as soon as any caller starts Telegram control again after a timed-out stop.

An old worker can also call `get_connection` after release and publish a new connection generation. That was observed on thread 16048: connection 1 was closed, then the worker published connection 2.

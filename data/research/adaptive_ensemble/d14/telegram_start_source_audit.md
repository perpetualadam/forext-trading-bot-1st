# Telegram start source audit

`start_telegram_control` is `forex_bot/telegram_control.py` lines 1177–1213.

Before D.14 every normal path returned `None`:

- Commands not enabled, lines 1186–1189. A configured bot still logs that commands are disabled.
- A dead stored worker is reaped at lines 1191–1193.
- A live stored worker returned at the old line 1184 without reading the stop event.
- A new thread is stored before `Thread.start()` and the stop event is cleared only on that creation path.
- `except Exception` around construction and `start()` clears the reference and logs that trading continues. `KeyboardInterrupt` is a `BaseException` and still propagates.

The lifecycle lock is `_poller_lock`. There was no public start-result constant.

After D.14 those same branches return `START_DISABLED`, `START_REFUSED_PREVIOUS_WORKER`, `START_ALREADY_RUNNING`, `START_FAILED`, or `START_STARTED`. The worker-creation decision is unchanged.

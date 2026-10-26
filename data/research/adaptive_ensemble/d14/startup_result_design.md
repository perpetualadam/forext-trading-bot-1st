# Startup result design

String constants at `forex_bot/telegram_control.py` lines 129–133:

- `START_STARTED`: `Thread.start()` returned for a new worker.
- `START_ALREADY_RUNNING`: the stored worker is alive and the stop event is clear.
- `START_REFUSED_PREVIOUS_WORKER`: the stored worker is alive and the stop event is set. No new worker. The event stays set.
- `START_DISABLED`: `commands_enabled()` is false, including an unconfigured bot. No worker.
- `START_FAILED`: the existing `except Exception` around thread construction and `start()` handled the failure.

The result is returned from the branch that decided it. There is no cached global result.

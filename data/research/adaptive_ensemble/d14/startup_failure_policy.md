# Startup failure policy

The existing `except Exception` still swallows thread-construction and `Thread.start()` errors, clears the worker reference, and logs that trading continues. It now also returns `START_FAILED`.

`KeyboardInterrupt` is not an `Exception`. An injected interrupt still left `start_telegram_control`. The following normal start recovered with `START_STARTED`.

No new exception category is swallowed. A result string does not become an application startup exception. `app.py` logs a static internal-failure line for `START_FAILED` and continues.

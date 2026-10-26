# Protected-state abort design

`lifespan` calls `initialise_fail_closed()` and then raises `StartupSafetyAbort` unless `live_safety_initialised()` is true.

The exception is not caught in `lifespan`. FastAPI startup would fail. That host was not started.

The message and log contain the reason code only. They do not contain the safety document, a token, or a database password.

No retry loop surrounds the check. A protected file is not passed to a repair writer.

Downstream calls stay in place for the valid path: database, order load, reconcile load, `build_api`, account summary, reconciliation, and the four background tasks. They are textually after the `raise`.

A valid BLOCKED document makes `live_safety_initialised()` true, so this raise does not treat ordinary BLOCKED state as corrupt.

No new authorisation flag was added.

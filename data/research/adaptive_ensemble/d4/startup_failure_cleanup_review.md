# Startup failure and cleanup review

STATICALLY_VERIFIED. Lifespan was not executed.

The preflight raise is before `get_connection()`, `build_api()`, account summary, reconciliation, `create_task`, and `start_telegram_control()`.

On that path no background task is created, no database connection is opened by `get_connection()`, and no broker client is built by `build_api()`. Cleanup is not required because those objects are not created. The `finally` block that cancels tasks is attached to the `yield` and does not run when startup raises first.

Repeated calls of `initialise_fail_closed()` on a future-schema fixture leave the bytes unchanged. OFFLINE_TESTED on the safety function. The lifespan source has no retry loop in the guard.

Failure logs use `reason=%s` with the reason code. The new message does not include the document.

Importing `app.py` still imports modules that know how to reach the database and the broker. Those calls that actually connect or request data are inside `lifespan` after the guard. This stage did not import `app.py`.

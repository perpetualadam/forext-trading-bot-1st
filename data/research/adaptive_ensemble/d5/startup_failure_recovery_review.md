# Stage D.5 startup failure and recovery

## PROTECTED_STATE_ABORT

Corrupt JSON, a future schema, an invalid document, an unreadable file, and a permission error all take `_refuse_existing`. The file bytes stay as they were. `lifespan` logs the reason code and raises `StartupSafetyAbort`. The exception is not caught inside `lifespan`.

Because the raise happens before `yield`, the `finally` block does not run. No database call, broker call, reconciliation call, or `create_task` runs. There is no task to cancel and no connection to close on this path.

A permission error is classified as unreadable. It does not take the missing-file path and does not create a new BLOCKED document over the unreadable file.

## VALID_BLOCKED_STARTUP

A valid BLOCKED document, a valid document whose persisted state is ALLOWED, and a missing file that can be created all set the public flag true and leave effective authorisation BLOCKED. Strategies stay inactive unless the synthetic document contains a boolean `true`, which these fixtures did not.

The observed order after the guard is `get_connection`, open-order load, reconcile-state load, `build_api`, account summary, `run_reconciliation_once`, operational-event load, alert, four `create_task` calls, then `start_telegram_control`. All of those were fakes. Shutdown then calls `stop_telegram_control` and cancels the four tasks.

## OTHER_STARTUP_FAILURE

A failed `os.replace` during the safety write sets `_state_valid` false with reason `persistence_failure` and aborts before `get_connection`. The original bytes remain.

A failure after `get_connection` or `build_api` was not injected. That path is untested. Its cleanup would be the `finally` block only if execution had passed `yield`. A failure between the guard and `yield` would skip `finally`. No production recovery was attempted.

## Logging

Abort messages contain the reason code. They did not contain the synthetic marker stored in the future-schema fixture, and they did not contain the document body. Tokens were empty in this process, so the run does not prove redaction of a real secret that was never present.

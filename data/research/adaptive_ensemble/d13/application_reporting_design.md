# Application reporting design

D.13 changes only `forex_bot/app.py`.

`lifespan` captures `stop_status = stop_telegram_control()`. A stop exception still sets `telegram_stop_failed` and goes through `_record_cleanup`.

Otherwise `_note_telegram_stop` applies this policy:

- `None`, `STOP_COMPLETED`, and `STOP_NOT_RUNNING`: no warning and no diagnostic.
- `STOP_INCOMPLETE_WORKER_ALIVE`: `logger.warning` with the static text `D12-STOP-01 Telegram shutdown incomplete: polling worker remains alive after bounded join.` The cleanup list gains `D12-STOP-01`.
- Any other value: a static unrecognised-status warning and `D12-STOP-UNKNOWN`. The value itself is not logged.

The diagnostic is appended to `_last_cleanup_errors` after exception type names and database release notes. It is not placed in `secondary`, so a successful shutdown does not raise. It does not set `telegram_stop_failed`, so database release rules stay as they were.

Task cancellation, task awaiting, startup preflight, broker setup, and trading behaviour are unchanged.

Startup-refusal reporting is omitted because Gate B found no supported interface.

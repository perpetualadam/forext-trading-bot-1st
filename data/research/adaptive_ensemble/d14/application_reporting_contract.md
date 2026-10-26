# Application reporting contract

`lifespan` calls `_note_telegram_start(start_telegram_control())` at `forex_bot/app.py` line 417.

`_note_telegram_start` is lines 99–122.

- `None`, `START_STARTED`, `START_ALREADY_RUNNING`, and `START_DISABLED` produce no refusal warning.
- `START_REFUSED_PREVIOUS_WORKER` logs the static `D12-START-01` warning.
- `START_FAILED` logs that startup failed internally and trading continues. It does not raise.
- Any other value logs that the status is unrecognised. It does not raise and does not claim success.

D.13 `_note_telegram_stop` is unchanged. `startup_cleanup_errors()` still receives `D12-STOP-01` and `D12-STOP-UNKNOWN` from the stop path only. Database release and task cleanup are unchanged.

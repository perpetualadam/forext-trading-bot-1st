# R.78 Linux operational integration

Phase D status: `NOT_VERIFIED`.

`run_startup_and_one_iteration` lives in `forex_bot/bot_loop.py` and was not imported on Linux. The import stops on `numpy`. `oandapyV20` is also absent. No second trading cycle was written, and the missing modules were not replaced with mocks.

What did run on Linux, separately from that harness:

- `execute_startup_sequence` with a synthetic `COMPLETE_EMPTY` snapshot, temporary SQLite on ext4 `/tmp`, and the real recovery lock.
- `live_management_permitted()` before recovery, after a completed recovery, and after the fencing epoch changed.
- A second `execute_startup_sequence` while another process held the recovery lock. Result: `RECOVERY_BLOCKED` / `recovery_already_in_progress`.
- Repair, investigation, and protocol fixture tests in `test_r78_liveness_and_protocol.py`: 21 passed on WSL.

What that does not show:

- `_execute_bot_cycle` was not called.
- Durable rows were not loaded through the operational one-iteration harness.
- The management function inside `bot_loop` was not executed on Linux.
- No synthetic OANDA client was attached to the real cycle on Linux.

`LINUX_INTEGRATION_NOT_VERIFIED` stays for the operational startup and management path.

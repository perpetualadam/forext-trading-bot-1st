# R.83 entry process-kill recovery

`test_03_process_kill_after_entry_commit_reconstructs_once` is a separate OS process. Mode `entry-memory` pauses inside the position-book assignment after `commit_verified_entry`. The parent sees the barrier and one recorder row, then calls `process.kill()` and `communicate`.

A second process runs `execute_startup_sequence` with a snapshot taken from the durable row (`R83_VIEW=match`).

Executed successor output contains:

- `manageable=1`
- `entry_outcome=ENTRY_FINALISED`
- `durable_trade=T-R83`
- `units=1000.0`

Recorder count stays 1. After the successor exits, the parent opens the journal and a second `begin_entry_submission` for `client-r83` raises `JournalUnavailable`. `managed_positions` count is 1.

The recovered position uses the account binding, instrument, trade id, direction, and units stored by the committed entry. No second OrderCreate is sent. The successor's startup owns the new fencing epoch. The killed process cannot publish after it is dead.

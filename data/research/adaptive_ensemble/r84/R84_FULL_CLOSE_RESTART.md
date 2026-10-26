# R.84 full-close restart

`test_09_full_close_kill_and_successor` starts `race_worker.py` in mode `full-hold`. The worker uses the documented negative `tradesClosed` shape, commits `CLOSE_FULLY_CONFIRMED`, and waits. The parent sees one recorder row and calls `process.kill()`.

The successor runs `execute_startup_sequence` with an explicit empty snapshot. Its output contains `close_state=CLOSE_FULLY_CONFIRMED`, `confirmed=1000`, `remaining=0`, and `manageable=0`. The recorder stays at 1. No second PositionClose is sent.

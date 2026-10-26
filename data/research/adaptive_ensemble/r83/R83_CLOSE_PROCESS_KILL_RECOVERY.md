# R.83 close process-kill recovery

`test_06_process_kill_before_close_removal` starts `race_worker.py` mode `close-hold`. The worker runs real startup, persists a 1000-unit EUR_USD position, runs `run_guarded_live_close`, and only then waits on the barrier. The parent observes one recorder row and kills the process before `close_confirmed_live_position`.

The successor uses `R83_VIEW=empty`, a complete empty synthetic book.

Executed output contains:

- `close_state=CLOSE_FULLY_CONFIRMED`
- `confirmed=1000`
- `remaining=0`
- `manageable=0`

Recorder count stays 1. The empty snapshot is explicitly `COMPLETE_EMPTY`. The test does not describe it as a broker-confirmed flat account beyond that fixture. The position is not manageable, so it is not republished as live exposure. No second PositionClose is sent. The permit remains consumed because the killed worker had already claimed it and the successor does not reset it.

# R.84 stale-owner fencing

`test_12_conflicting_snapshot_and_stale_owner` confirms a documented full close in the parent. A child then runs real startup against a snapshot that still shows 1,000 units. The child prints `manageable=0`.

The parent's `close_confirmed_live_position` returns `None`. The journal stays `CLOSE_FULLY_CONFIRMED` rather than `CLOSE_FINALISED`. A later close on that position does not add a PositionClose.

`positions.py` is unchanged at `b9da0d1da27e298919eff3a889ff4ec83a53baf95b320876839207ab6827153e`. The epoch fence added in R.83 still returns before the pop when this process has an epoch and that epoch is no longer current. `entry_journal.py` is also unchanged, so a finalised entry is still protected from an ambiguous overwrite.

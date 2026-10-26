# R.8 and R.9 regressions

The prior synthetic suites passed in a separate process: 120 passed, 7 skipped, 1 deselected. The R.10 suite passed in another process: 69 passed, 5 skipped.

PENDING, PARTIAL, and UNRESOLVED still block a new client id. FILLED still does not prove exposure is closed. A missing position still blocks. A flat token still cannot clear an unresolved order. Invalid direction and an inactive strategy still stop before dispatch. Live-order auth stays BLOCKED.

The R.8 source assertion now finds `RESERVATION_BLOCK_SQL` between the advisory lock and the insert. The constant still contains the status check, and it also blocks an unmarked FILLED row. The R.9 assertion checks the same constant for `exposure_safety`. Those updates follow the repaired SQL. They do not allow a new reservation while a legacy FILLED row is uncertain.

`bot_loop.py` was not modified.

# R.81 ambiguous close restart

Evidence class: executed `test_14`, with the crash successors in `test_05`, `test_06`, and `test_07`.

The parent completes recovery, consumes one close permit, and records one PositionClose that times out. The state is `CLOSE_OUTCOME_AMBIGUOUS`.

A fresh process with `COMPLETE_EMPTY` and a fresh process with the trade still open both leave the row ambiguous, leave `network_permit` at 1, and add no recorder row. Neither prints `close_state=CLOSE_FULLY_CONFIRMED`.

Observation-only rows are not created by this test. The close path still refuses a position that fails `position_management_permitted`, which the R.80 observation test continues to cover. This restart test shows that a new epoch does not release the consumed close permit and that a flat or still-open snapshot does not confirm it.

`R81_AMBIGUOUS_CLOSE_RESTART_VERIFIED`: PASS.

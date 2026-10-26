# R.84 ambiguous close restart

`test_11_ambiguous_restart_sends_no_second_close` uses a TransactionDetails body that has fill units and no `tradesClosed` or `tradeReduced`. The worker commits that unresolved close and is killed.

The successor uses a snapshot that still shows 1,000 units and runs one cycle. Output contains `manageable=0` and `cycle=1`. It does not contain `CLOSE_FULLY_CONFIRMED`. The recorder stays at 1. The missing reduction is not turned into a full close, and the restart does not send another PositionClose.

# R.84 partial-close restart

`test_10_partial_kill_quarantine_and_ratchet` kills the worker after a `tradeReduced` confirmation of 400. The successor snapshot matches the durable 1,000-unit row and runs one `_execute_bot_cycle`.

Output contains `CLOSE_PARTIALLY_CONFIRMED`, confirmed 400, remaining 600, `durable_units=1000`, `ratchet=40`, `manageable=0`, and `cycle=1`. The recorder stays at 1. The successor does not publish a manageable 600-unit position and does not send a second close.

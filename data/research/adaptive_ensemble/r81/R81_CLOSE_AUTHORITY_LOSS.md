# R.81 close authority loss

Evidence class: executed `test_03`, `test_04`, and `test_10`.

`test_03` is an authorised owner, not a cold process. The position is a durable EUR_USD row with one trade id and the synthetic account binding. The child completes startup, claims the close permit, and blocks in `acquire_oanda_rest_slot`. The parent completes a successor startup. The child then continues and the R.81 check refuses PositionClose.

The recorder count is 0. The close is not `CLOSE_FULLY_CONFIRMED`. `network_permit` remains 1. A later fresh process does not submit.

`test_10` fences a close owner before it submits. The recorder stays 0 and the output is not a full confirmation.

`test_04` shows that a current owner still gets exactly one confirming PositionClose.

`R81_STALE_OWNER_CLOSE_REFUSED`: PASS.

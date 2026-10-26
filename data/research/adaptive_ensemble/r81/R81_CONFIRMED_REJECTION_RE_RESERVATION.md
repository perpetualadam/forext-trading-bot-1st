# R.81 confirmed rejection and re-reservation

Evidence class: executed `test_11` under a completed recovery session. The historical R.74 test was not edited.

The synthetic PositionClose body is `longOrderRejectTransaction` with id `RJ`. `interpret_close_response` returns `CLOSE_REJECTED_CONFIRMED` / `broker_reject_or_cancel`. The first operation stays in the journal with `network_permit=1`. That permit is not reused.

A later `run_guarded_live_close` on the same live position creates a different `operation_id`, requires the still-valid recovery authority, and uses a new permit. The second synthetic result is a full fill and reaches `CLOSE_FULLY_CONFIRMED`. PositionClose count is 2 because these are two durable operations, not a retry of the first.

This matches the existing state machine. `CLOSE_REJECTED_CONFIRMED` is in the released set, so `blocking_trade` does not keep the obligation open. No policy was widened.

`R81_CONFIRMED_REJECTION_RE_RESERVATION_VERIFIED`: PASS.

A timeout is not this path. `test_12` shows the timeout stays `CLOSE_OUTCOME_AMBIGUOUS`, keeps the same operation id, and does not add a second PositionClose.

`R81_AMBIGUOUS_CLOSE_RE_RESERVATION_REFUSED`: PASS.

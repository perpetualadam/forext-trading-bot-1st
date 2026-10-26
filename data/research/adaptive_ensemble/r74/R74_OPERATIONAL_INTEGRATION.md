# R.74 Operational Integration

`run_guarded_live_close` (`broker_close_evidence.py` lines 615–780):

1. Refuses a non-permitted or non-live row before any journal write.
2. Opens the journal. A missing or unauthorised journal returns without a broker call.
3. Returns an existing unresolved journal row without a new submission.
4. Checks `assert_broker_order_allowed` before the journal insert. A disabled broker does not create a durable reservation.
5. Commits `reserve`, then `commit_submission_intent`.
6. Checks the owner token and the current position identity.
7. Calls `_submit_position_close_body`.
8. Persists timeout, rejection, partial, and full results through `journal.mark`.

The position-close body is unchanged. Client extensions are still not sent. They were not treated as an idempotency key in R.73, and R.74 does not add that claim.

`bot_loop.py` deletes a live row only through `close_confirmed_live_position`. Profit-protection activation, ATR, the four-pip fallback, the ratchet, weekend flattening, and the entry block were not edited.

`broker_protection.py` was not edited. `broker_sl_tp_hit` still returns false. Snapshot classification in `reconciliation.py` was not retuned. `COMPLETE_EMPTY` and `INCOMPLETE` remain distinct. A flat book still cannot delete a live row without an identity match.

`oanda_exec.py` was not edited. The guarded path is the manage-path writer. `execute_trade` remains for non-live manage closes and any historical live caller outside the manage branch. Those callers do not receive a new close trigger.

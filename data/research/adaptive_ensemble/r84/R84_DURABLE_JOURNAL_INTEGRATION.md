# R.84 durable journal integration

`test_07` and `test_08` use a disposable schema-5 journal, real `execute_startup_sequence`, a persisted managed position, `run_guarded_live_close`, one synthetic PositionClose, and synthetic TransactionDetails.

Full close: one PositionClose, `CLOSE_FULLY_CONFIRMED`, confirmed 1,000, remaining 0. The in-memory row remains until `close_confirmed_live_position`. That call removes it while this process still holds the fencing epoch. The journal then becomes `CLOSE_FINALISED`.

Partial close: one PositionClose, `CLOSE_PARTIALLY_CONFIRMED`, confirmed 400, remaining 600. Position units stay 1,000. The second close call does not send another PositionClose.

`_apply_verified` no longer replaces the operation's account binding with the classifier label `matched`. `close_confirmed_live_position` compares that binding with the journal row. Replacing it with `matched` made a confirmed close fail the comparison for the current owner as well as a stale owner. The R.83 epoch fence is unchanged.

No schema change, no new broker-write sink, and no permit release.

# R.70 Remaining Risks

Production trading remains NO-GO.

## Known unsafe behaviour that R.70 left in place

- A permitted live row, `RECONCILE_ACTION=auto_fix`, and a structurally valid `positions: []` still reach `account_disappeared_broker_position`. The local row can be removed while `PositionClose` is not sent. Trade details may be queried. This does not prove the bot's close filled. R66-10 and R66-11 remain open.
- `broker_sl_tp_hit` still returns false. Local stops are not broker stops. R66-03 and R66-05 remain open.
- There is still no close idempotency key.
- Sizing and account-currency assumptions were not corrected. R66-07 remains open.
- New entries stay blocked. That is the safe state, not a completed trading system.

## Limits of the R.70 control

- No broker timestamp is available on this response path. `STALE` is not a time-to-live.
- A newer failed request can discard an older success that has not published yet. The last published book remains.
- The reconcile report dictionary can be overwritten by a slower cycle.
- `_remember_broker_snapshot` does not check generation.
- Nets are stored as `float` after `Decimal` validation.
- The shadow engine's local restore and the account adapter are separate readers. The adapter already rejects a missing positions list. The shadow reader is not a broker snapshot.
- Linux did not import `oandapyV20`. `LINUX_INTEGRATION_NOT_VERIFIED`.
- PostgreSQL was refused by the harness. `POSTGRESQL_INTEGRATION_NOT_TESTED`.
- No real broker call was made. `REAL_NETWORK_EXECUTION_NOT_TESTED`.

## Not verified

- Legacy pytest modules that import operational config.
- The production entry tail, by design.
- Full `_evaluate_impl` running at the same time as an invalid snapshot. The book does not change on that snapshot, and `bot_loop.py` was not edited.
- Restart behaviour of the new generation counter. It is process memory.
- Profitability. R66-19 was not assessed. No performance figure is claimed.

## Intentionally isolated

- R.67B close state machine.
- R.62–R.65 containment experiments.
- Source-gate enablement and `one_session.permit`.

## Future work

Stage 2 is broker protection evidence. Do not start it automatically. Do not enable trading.

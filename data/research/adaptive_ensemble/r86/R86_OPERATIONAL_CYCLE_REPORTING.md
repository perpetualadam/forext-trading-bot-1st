# R.86 Operational Cycle Reporting

Evidence: `test_57` and `test_58` called `_execute_bot_cycle` after a real partial close and `execute_startup_sequence`. `run_bot` was not called. The report function is not called by the cycle.

Setup: disposable schema-5 journal, synthetic broker, BUY 1,000 EUR_USD, confirmed close 400, remainder 600, ratchet 40, permit consumed.

Incomplete startup view:

- Startup state `RECOVERY_BLOCKED`.
- Cycle recorded no `OrderCreate` and no second `PositionClose`.
- Close state, remaining units, and `network_permit` matched the pre-cycle row.
- Ratchet stayed 40.
- A separate report on that row showed remainder 600, a failed observation as unknown, `flat` false, and `broker_requests` 0.

Conflicting 1,000-unit startup view:

- No decision was manageable.
- The in-memory book keys were unchanged by the cycle.
- No `OrderCreate` and no second close.
- The permit file stayed absent.

The report stayed disconnected because connecting it to `daily_report` or the entry path would mix an unverified observation into a figure the cycle already uses for managed exposure. The limitation is intentional.

Candle loading logged a missing decision frame because the synthetic candle list was empty. Account summary logged a mismatch. Neither was an order.

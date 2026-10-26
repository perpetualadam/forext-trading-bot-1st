# Integrated safety ordering

The shared path order after the existing permission, position, exposure, strategy, vote, and RL gates is:

1. Market-data validation (`_market_entry_block`).
2. Accepted account snapshot.
3. Daily-loss and drawdown, only when `DECISION_REPAIR_ACCOUNT_RISK` is on.
4. Existing sizing on the accepted equity.
5. Unit cap, only when `MAX_POSITION_UNITS` is above zero.
6. Portfolio stop-risk cap on the same equity.
7. Gross notional, only when the percentage is above zero, including pending notional.
8. Margin evidence recorded as not implemented.
9. Existing reservation.
10. Inert recording adapter.

A BUY vote, a SELL vote, an RL approval, and an active strategy flag still pass through the quote and lookback checks. Failed checks return before reservation. Historical FILLED, PENDING, PARTIAL, and UNRESOLVED holds still return earlier. `confirm_exposure_flat` still returns false. `execute_oanda_market_open` still appears once, inside `production_execution_adapter`, which the tests do not call.

A valid synthetic BUY and a valid synthetic SELL each reached `FakeBroker` once.

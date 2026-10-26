# Risk and position sizing

J33–J52 passed. Formulas were not changed.

- A 10,000 balance and a 0.002 stop produce a positive size through `position_sizing`.
- Zero and negative balances return no positive size, so the seam does not dispatch.
- A zero stop returns 0 from `position_sizing`. The production loop does not have that early return when the notional percentage is 0. The seam refuses the dispatch and records the gap.
- A negative stop is absolute-valued by the existing formula and still sizes.
- A non-finite stop stops before dispatch.
- The default formula uses `max(units, 1)` once risk is positive, so there is no separate below-minimum rejection on that path.
- `MAX_POSITION_UNITS` defaults to 0, so the unit cap is off.
- The gross notional cap is off when its percentage is 0. The portfolio stop-risk cap is on and blocked both a 1,000,000 balance and a second symbol.
- An open position, unconfirmed exposure, a pending reservation, a partial reservation, an unresolved reservation, and a historical FILLED row all stop before the fake broker.
- With persistence disabled, `broker_entry_block_reason` returns `recovery_unreadable` and does not open PostgreSQL.
- Daily-loss and drawdown checks exist behind `DECISION_REPAIR_ACCOUNT_RISK`. That flag is off by default and was not enabled.

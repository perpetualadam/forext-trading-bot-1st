# Remaining blockers

1. `run_bot` was not executed. The continuous loop is NOT_EVALUATED.
2. The old `_evaluate_impl` broker tail remains in source and is not reached. The shared decision fail-closes before it. Real broker classification was not executed.
3. The shared decision does not call `select_strategy`, `ai.vote`, or the RL gate. Those inputs are injected for the offline boundary.
4. No authorised broker-flat release exists. A successful release is NOT_EVALUATED.
5. Recovery SQL still treats a stored `CONFIRMED_FLAT` marker as a reason to omit a historical FILLED row. Nothing in the order path writes that marker. The function argument can no longer clear a hold.
6. PostgreSQL did not execute SQL. OANDA was not contacted.
7. Spread, short lookback, the default unit cap, and the default gross notional cap remain as recorded in R.12. Daily-loss and drawdown checks stay behind `DECISION_REPAIR_ACCOUNT_RISK`.

# Remaining integration gaps

1. `run_bot` does not call the new seam. The continuous loop is untested.
2. Synthetic candles fail `decision_frame_rejection` with `missing_provenance`. The simulation records that and still reaches the fake broker. A real broker open would stop. No live seal was forged.
3. The seam does not call `select_strategy`, `ai.vote`, or the RL gate. Those inputs are injected.
4. Excessive spread, a malformed spread, and a short lookback are not hard blocks in the current source.
5. A negative stop is absolute-valued. A zero stop returns no units, and the production loop does not return at that point when the notional percentage is 0.
6. `MAX_POSITION_UNITS` defaults to 0. The gross notional percentage defaults off. Portfolio stop-risk is on. Daily-loss and drawdown checks stay behind `DECISION_REPAIR_ACCOUNT_RISK`, which is off.
7. `confirm_exposure_flat` still accepts the token `CONFIRMED_FLAT` if some other caller invokes it. This seam does not.
8. PostgreSQL did not execute the reservation SQL.
9. No OANDA request was made. No production reconciliation ran. Profitability was not measured.

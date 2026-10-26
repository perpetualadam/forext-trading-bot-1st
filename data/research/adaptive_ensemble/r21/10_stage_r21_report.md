# Stage R.21

**Classification: `R21_OFFLINE_SELECTOR_AND_ORDER_STATE_INTEGRATED`**

The shared iteration now uses the selector's result. A valid `select_deterministic` result of `scalp` controlled the FILLED cycle and ignored a supplied `trend`. A null result blocks with `NO_STRATEGY_SELECTED` before sizing, reservation, and dispatch. An ambiguous attempt is stored as local status `UNRESOLVED` with the exposure hold kept, and the next cycle blocks without a retry.

## Answers

- **Why did R.20's selector return null?** `select_strategy` only allocates among active strategies. All six are inactive, so the result is null. The iteration then used the caller-supplied `scalp`.
- **Can the actual selector produce a valid strategy?** `select_strategy` on the default path cannot, and this stage does not activate a strategy. `select_deterministic` can: with an offline eligibility map it returned `scalp` and did not change `strategies[name].active`.
- **Did a real selector result determine the chosen strategy?** Yes. The FILLED cycle used that `scalp` result. The supplied name was `trend` and was ignored.
- **Does null now block?** Yes. `NO_STRATEGY_SELECTED`, with zero reservation attempts and zero adapter calls.
- **Can a caller-supplied strategy override selection?** No. It cannot replace null, and it cannot replace a different valid selection.
- **What is the correct ambiguous-order representation?** Local status `UNRESOLVED`, plus the existing unresolved-intent marker and `exposure_unconfirmed`. `PARTIAL` stays `PARTIAL`. `FILLED` stays `FILLED`. Both keep the exposure hold.
- **Does cycle 2 still block?** Yes. The FILLED cycle stops with `position_already_open` after reading `exposure_unconfirmed`. The ambiguous cycle stops with `exposure_unconfirmed`. Neither reserves or dispatches again.
- **Did any safety regression fail?** No. R.8 through R.20 completed with exit 0. R.10 did not hit `WinError 5`.
- **Were any application files besides `bot_loop.py` modified?** No.
- **Did any broker, database, or network operation occur?** No successful broker call, PostgreSQL connection, or network or DNS lookup. The isolation barrier recorded blocked attempts only.

## Evidence

24 R.21 tests passed. The real `evaluate` path ran. `select_strategy` returned null and that case blocked. `select_deterministic` returned `scalp` and that name was the strategy on the decision and the order. Hybrid `select_strategy` returned an inactive name and blocked. Unknown and malformed results were test doubles, not production selector output.

R.20's two-cycle counts remain 30 passed. Production eligibility stayed false. The production adapter rejected the synthetic decision and a forged eligibility flag with zero calls to `execute_oanda_market_open`.

`bot_loop.py` SHA-256 is `081314246ce22fa092d6f7de9ef8f84760bf87e086f5838e763fb08d7f34f55f`. HEAD remains `d080d897945bc44fa37c02caab504ed707146bec` on `main`.

Restart durability of the new in-memory `UNRESOLVED` status was not evaluated.

**PRODUCTION DEPLOYMENT: NO-GO.**
**PRACTICE ORDERS: NOT AUTHORISED.**
**LIVE TRADING: NOT AUTHORISED.**
**ROLLBACK: NO-GO.**

End of stage R.21. No further stage was started.

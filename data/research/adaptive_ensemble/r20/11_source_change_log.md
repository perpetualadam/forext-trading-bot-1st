# Source change log

Application source modified: `forex_bot/bot_loop.py`.

Post-stage SHA-256: `248269d4deaa79947cc039708815119cce800a0baffbd434aa56c708041beefd`.

Pre-stage SHA-256: `9b6327045e29adc48f37ed81d13db44e216e24e71326284dc6c80079e2e74550`.

Changes:

- Added `_unified_market_snapshot` and `_bound_entry_quote`.
- After the market checks, BUY sizing uses the ask and SELL sizing uses the bid from that snapshot. The same quote is stored as the entry quote on the inert request and on the sealed binding.
- A non-finite injected price still blocks. A differing finite injected price is ignored and recorded.
- The position phase now records the exposure-hold read before the existing position gate returns.
- The AI vote direction is stored on the iteration evidence.
- `position_sizing` and the portfolio formula were not changed.
- `app.py`, `database.py`, and `orders.py` were not modified.

Tests: `tests/test_r20_two_cycle.py`. Hash pins in the R.8, R.10, and R.11 tests match the new `bot_loop.py` hash.

Protected files were not modified.

# Single-iteration seam

CODE MODIFIED in `forex_bot/bot_loop.py`.

`evaluate_one_instrument_iteration(symbol, dependencies)` is synchronous. Tests call it directly. `run_bot` and `_evaluate_impl` were not rewritten and were not executed.

The seam calls the existing functions:

- `flatten_for_weekend_at` and `in_active_session_at` with an injected clock
- `exposure_entry_block_reason`
- `pre_trade_entry_blocked_reason`
- `strategy_entry_block_reason` and `continue_entry_after_strategy_gate`
- `compute_indicators` and `volatility_ok`
- `direction_action_gate`
- `decision_frame_rejection`
- `position_sizing` and `cap_position_units`
- `notional_cap_decision`, `portfolio_risk_cap_exceeded`, `usd_direction_guard_decision`
- `try_begin_order_submission`
- `finalize_order_fill`, `mark_order_failed_or_cancelled`, `record_synthetic_fill_position`
- `note_unconfirmed_exposure` and `restore_unresolved_intent`

A fake broker `submit` runs only when `dependencies.simulation` is true and the real live-order gate returned a block. If that gate returns no block, the seam refuses to dispatch. Production strategy objects are not activated. The seam does not set `LIVE_ORDERS_ALLOWED`.

Broker modules are imported inside the production functions that need them. Importing the seam does not construct an OANDA client. `position_sizing` still imports `trading.py`, and that module imports the broker execution module. The tests assert `oanda_client._api` stays `None`.

Synthetic frames have no live provenance seal. `decision_frame_rejection` returns `missing_provenance`, which would stop a real broker open. The simulation records that result and continues only to the fake broker. Invalid prices, missing OHLC, and a non-finite stop still stop before dispatch.

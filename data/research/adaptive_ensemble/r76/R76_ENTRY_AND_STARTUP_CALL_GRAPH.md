# R.76 entry and startup call graph

## Live entry

1. `evaluate_one_instrument_iteration` (`forex_bot/bot_loop.py` line 3324) remains the decision function.
2. `dispatch_production_iteration` (line 4487) delegates to that function.
3. When `dependencies.simulation` is false, the iteration assigns `production_execution_adapter` and returns `production_execution_adapter_withheld` (line 4296) before any call. That withhold was not removed.
4. `production_execution_adapter` (line 3171) still calls `production_adapter_refusal` (line 2898) first. A refusal returns `broker_called: False`.
5. Only after that refusal is empty does the adapter call `begin_entry_submission` (line 3217) and then the single `execute_oanda_market_open` (line 3249) with `entry_permit`. `bot_loop.py` contains that name once.
6. The legacy broker tail still returns before `OrderCreate`. It was not re-enabled.

No current producer seals `production_eligible` true, so the adapter's success branch is not reached by the production iteration. The journal is an additional fence for a call that has already passed the existing refusal function. It does not grant entry authority.

## Order construction and submission

`execute_oanda_market_open` requires keyword-only `entry_permit` and passes it to `_place_market_order_open_sync` (`forex_bot/oanda_exec.py` line 554).

`_place_market_order_open_sync` calls `_submit_order_create` (line 484).

`_submit_order_create` order:

1. Refuse a missing `EntrySubmissionPermit` with `EntryGuardRefusal`.
2. Call `assert_new_live_exposure_allowed(action="open")`. The default live-order authorisation remains blocked.
3. Call `require_order_quote`.
4. Call `claim_entry_permit` and commit `network_permit = 1` before `get_api`.
5. Build one `MarketOrderRequest` with `positionFill=OPEN_ONLY` and `clientExtensions.id` set to the client order id.
6. Construct the only `oanda_orders.OrderCreate` (line 533) and call `api.request`.

A timeout after the claim is marked `ENTRY_OUTCOME_AMBIGUOUS` in `_place_market_order_open_sync` before the exception propagates. The same client id cannot be reserved again while the row is unresolved.

## Response and identity

`_parse_open_fill` (line 364) still returns the fill transaction id. Callers must not treat that value as the trade id.

`record_entry_response` (`forex_bot/entry_capture.py` line 18) classifies the body. The managed `Position.broker_trade_ids` receives `tradeOpened.tradeID`. `Position.broker_order_id` is left empty so `local_broker_trade_ids` (`forex_bot/broker_exit.py` lines 105–117) returns one id. The order transaction id stays on `entry_operations.broker_order_id`.

Publication happens only after `persist_bot_position` commits and the symbol slot is empty or already holds the same position instance.

## Startup and management

`run_bot` (line 4498) calls `execute_startup_sequence(load_startup_broker_view())` at line 4502, before `while True` at line 4504. This stage did not call `run_bot`.

`_evaluate_impl` (line 740) checks `live_management_permitted` at lines 796–802 before `apply_profit_protection`. A live position returns with `recovery_incomplete` when the state is not acceptable.

After a live `apply_profit_protection`, lines 871–875 call `persist_protection_progress`. A refused or failed write sets `recovery_quarantine` and returns before the close path.

The close path remains `run_guarded_live_close` for live positions. `trading.execute_trade` still raises before a live close.

## Broker writes that can precede durable evidence

`OrderCreate` is reached only after the entry reservation and the submission-intent commit, and after `claim_entry_permit`. A crash before the claim leaves `network_permit = 0`. A crash after the claim leaves the permit consumed. Neither path sends a second order for that client id.

`PositionClose` remains behind the R.75 close permit. The entry permit cannot be passed to it.

The SQLite commit and the in-memory `positions` assignment are separate. A crash between them is recovered by `execute_startup_sequence`, not by treating memory and disk as one transaction.

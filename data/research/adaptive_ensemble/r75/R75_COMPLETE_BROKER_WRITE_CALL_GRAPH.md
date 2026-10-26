# R.75 Complete Broker-Write Call Graph

Search scope: repository `*.py` for `PositionClose`, `PositionCloseRequest`, `OrderCreate`, `TradeClose`, `OrderCancel`, `OrderReplace`, `_submit_position_close_body`, `execute_oanda_market_close`, `_place_market_order_sync`, and `execute_trade`.

## Operational writers inside `forex_bot/`

| Site | Class | Reaches the broker only when |
| --- | --- | --- |
| `oanda_exec.py` lines 442–449 `oanda_positions.PositionClose` | Operational live-close writer | `claim_network_permit` updates exactly one matching row |
| `oanda_exec.py` line 535 `oanda_orders.OrderCreate` inside `_place_market_order_open_sync` | Operational entry writer | Existing entry gates. Not rewritten and not granted new authority |
| `oanda_exec.py` `fetch_trade_details_sync` line 626, `fetch_transaction_details_sync` line 651, `fetch_pending_orders_sync` line 608 | Read-only | No write endpoint is constructed |

No `OrderCancel`, `OrderReplace`, or `TradeClose` constructor exists under `forex_bot/`.

## Live-close chain that used to bypass the journal

```
bot_loop.py live branch, lines 1078–1084
  -> broker_close_evidence.run_guarded_live_close, line 615
    -> close_journal.reserve / commit_submission_intent / issue_submission_permit
    -> oanda_exec._submit_position_close_body, line 401
      -> claim_network_permit
      -> PositionClose, line 442

trading.execute_trade, line 358, execution_kind live
  -> RuntimeError at line 392
  -> does not call execute_oanda_market_close

execute_oanda_market_close, line 676
  -> _place_market_order_sync, line 462
    -> _submit_position_close_body
```

`bot_loop.py` lines 1097–1099 call `execute_trade` only in the non-live branch. That branch is paper, simulated, or window-paper bookkeeping. A caller that passes `execution_kind="live"` to `execute_trade` now raises before HTTP. `backtest.py` reaches `execute_trade`; a live kind is refused there too.

## Other mentions

| Location | Class |
| --- | --- |
| `data/research/adaptive_ensemble/r75/poc/close_worker.py` | Synthetic test recorder |
| `r74` and `r73` test fakes | Synthetic test |
| `r67/c/poc/reference_model.py` | Research-only label |
| `tests/test_g9_management.py`, `test_g9_1_candle_exceptions.py`, `test_market_provenance_g6.py`, `test_market_provenance_g7.py` | Legacy unit calls of `_place_market_order_sync` without a permit. They now fail at the signature. Not rewritten. |
| `tests/g12_1_verify.py` and `tests/test_g12_1_verify.py` | Source scanners and stub functions, not operational clients |
| `forex_bot/research/**` | Research-only string checks |

No dynamic construction of an OANDA write endpoint was found in `forex_bot/`. The final close boundary does not accept a boolean that skips the journal.

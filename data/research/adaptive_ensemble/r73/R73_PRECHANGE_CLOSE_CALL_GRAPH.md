# R.73 Pre-change Close Call Graph

Mapped before the R.73 edit. This is the graph that existed at the R.72 baseline.

## Manage-path triggers

`forex_bot/bot_loop.py` `_evaluate_impl`, after the R.68 ownership return:

| Trigger | Source | Effect before R.73 |
| --- | --- | --- |
| Broker SL/TP | `broker_sl_tp_hit` | Always false, so it did not request a close |
| Paper candle SL/TP | price compared with local stop and target | Could request a local close |
| Profit protection | `apply_profit_protection` | Could request a close. Formulas were not changed |
| Weekend flatten | `flatten_for_weekend` | Could request a close. Timing was not changed |

Those three request flags share one block. The block called `execute_trade` and then, if that call returned, `close_position`.

## Live submission

`trading.execute_trade` for `execution_kind == "live"` calls `oanda_exec.execute_oanda_market_close`.

That calls `_place_market_order_sync`, which sends `PositionClose`. The installed SDK class is `oandapyV20.contrib.requests.PositionCloseRequest`. It accepts optional `longClientExtensions` and `shortClientExtensions`. The pre-change call did not send them. The helper returned `(pnl, fill_price)` and discarded the response body. A returned tuple was treated as success, and `close_position` then removed the row.

`close_fill_path` returns `abort_broker_disabled` when live orders are off. That path returns before `execute_trade` and does not delete.

## Other callers

| Caller | Role |
| --- | --- |
| `positions.close_position` | Pops a permitted row. Observation rows are refused |
| `positions.close_local_position` | Calls `close_position` |
| `broker_exit.account_disappeared_broker_position` | On a flat book, popped a permitted live row even when trade or transaction lookup failed |
| `reconciliation.py` auto-fix | Calls that helper for a broker-backed permitted row when the published net is flat |
| `backtest.py` | Calls `execute_trade` and `close_position` outside the live manage loop |
| `research/adaptive_ensemble/portfolio_v2.py` | A separate research `close_position`. It is not the operational book |

No other operational `PositionClose` call site was found.

`R73_ALL_CLOSE_PATHS_MAPPED`

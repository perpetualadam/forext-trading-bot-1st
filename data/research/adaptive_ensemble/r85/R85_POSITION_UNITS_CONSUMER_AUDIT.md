# R.85 Position Units Consumer Audit

Evidence: source search for `.units` under `forex_bot`, plus the executed cycle in `test_26` and `test_44`. `position.units` was not globally changed to 600.

## What `Position.units` is

After a partial close it is still the original 1000, both in the process that submitted the close and on the quarantined object rebuilt from `managed_positions`. Journal remaining 600 is a different column.

## Consumers

| Consumer | Expectation if it ran | Reached while quarantined? |
| --- | --- | --- |
| `close_confirmed_live_position` identity check | Original requested units | No. Partial rows return before the pop. Quarantined rows fail `position_management_permitted`. |
| `bot_loop` management close around the live close call | Would size a close from `pos.units` | No. Management returns when the row is observation-only, and a quarantined row is not in `positions`. |
| `bot_loop` new-entry path | Would treat a missing `get_position` as flat | It was reachable. `_evaluate_impl` now returns when `symbol_has_quarantined_exposure` is true. The cycle test captured the log line `quarantined exposure`. |
| `run_guarded_live_close` | Requests `pos.units` | Refuses when management is not permitted. The cycle sent no second close. |
| `trading.py` stop-risk helpers | Current risk if called with the position | Not called for a quarantined row. The row is outside the book. |
| `portfolio_exposure.py` | Sums `positions` | Omits the quarantine dict, so a status total can understate broker exposure. It does not submit an order. |
| `reconciliation.py` auto-adjust | Compares book units with the broker net | Iterates `positions` and skips rows that fail `position_management_permitted`. The quarantined row is in neither set. |
| `broker_exit.py` | Close units from the resident position | Gated by management permission. |
| `profit_protection.py` | Price and ratchet, not a unit resize | File hash unchanged. Ratchet stayed 40. |
| Telegram and research portfolios | Display or research totals | Not on the live close path exercised here. |

## Overstatement check

Using 1000 as manageable exposure would overstate current exposure by the closed 400. That use was not reachable after the guard:

- Manageable decisions were false.
- `get_position` was `None`.
- `symbol_has_quarantined_exposure("EUR_USD")` was true.
- `_execute_bot_cycle` logged `quarantined exposure` and recorded no `OrderCreate` and no extra `PositionClose`.

The portfolio sum can understate exposure because it does not see the quarantine dict. That is a reporting gap, not a manageable-unit overstatement, and it was not changed. Sizing policy was not changed.

No consumer was switched from original units to 600.

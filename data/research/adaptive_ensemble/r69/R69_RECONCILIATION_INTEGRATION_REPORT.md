# R.69 reconciliation integration

Function executed: `forex_bot.reconciliation.reconcile_positions_log_only`.

Synthetic `OpenPositions` bodies. No `PositionClose` or `OrderCreate` call was recorded.

| Case | Setup | Observed |
| --- | --- | --- |
| 1 `log_only`, broker-only | `paper_broker`, `log_only` | Observation recorded. Managed book empty. Fixes `0`. Mismatch says broker open and no local position. |
| 2 Broker mode, broker-only | `live_broker`, `log_only` | Observation recorded. Managed book empty. Kind stored is `reconcile_import`. |
| 3 `auto_fix`, broker-only | `paper_broker`, `auto_fix` | Observation recorded. Fixes `0`. Authority false. |
| 4 `log_only`, paper plus broker | `paper_broker`, existing `window_paper` | Paper object unchanged. Observation stored separately. Fixes not a paper delete. |
| 5 `auto_fix`, same conflict | `auto_fix` | Paper units unchanged. Fixes `0`. Observation not permitted. |
| 6 Manual discovery | `EUR_GBP` with trade id `manual-1` | Observation only. |
| 7 Arbitrary trade id | `555001` | Stored on the observation. Management false. |
| 8 Caller-looking live kind | Operational OpenPositions path | The path has no execution-kind argument. Stored kind is `reconcile_import`. |
| 9 Later flat snapshot | Second cycle `positions: []` | Observation remains. Managed book stays empty. |
| 10 Incomplete body | Response `{}` with no `positions` key | `last_error` is none. Treated as an empty success. Paper row kept. No observation created. This is not fail-closed for exposure. It does not grant management. |
| 11 Failed snapshot | `request` raises | `last_error` set. Paper row unchanged. No observation. |
| 12 Both sides | Long 1000 and short 400 | One observation of 600 units. Not managed. |
| 13 Several trade ids | `A,B` | Both ids on the observation. Not managed. |
| 14 Unknown instrument | `FOO_BAR` | Not in the managed book. Observation, if recorded, is not permitted. |
| 15 Malformed payload | `positions` is a string | Fetch error. Paper row unchanged. |
| Numeric garbage units | units `nope` | No managed row and no observation. |
| Legacy observation already in the book | `auto_fix`, broker flat | Row remains. Fixes `0`. |
| Permitted live row, broker flat | `auto_fix` | Local live row is removed. Endpoint list has `TradeDetails` and no `PositionClose`. This is the pre-existing disappear path, not an observation grant. |

`clear_pending_broker_exit` attempts `psycopg2.connect` during an import. The guard rejects it. The managed book is still unchanged.

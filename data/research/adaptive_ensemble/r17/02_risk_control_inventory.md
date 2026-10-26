# R.17 risk-control inventory

Shared function: `evaluate_one_instrument_iteration` in `forex_bot/bot_loop.py`.

A production call with `simulation=False` still returns at the live-permission gate before strategy selection, the vote, the RL veto, sizing, and these risk checks. The inventory below is the shared path once that gate has allowed an isolated simulation.

| Control | Where | Input | Threshold | Enabled in production defaults | On shared path | Missing data | Before reservation | Before adapter | Survives next iteration | Survives process restart | Class |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Account snapshot | `_account_entry_block` | caller balance and context | isolated harness only | yes, fail closed | yes | blocks | yes | yes | no process memory of a pass | no | ACTIVE_AND_TESTED |
| Accepted equity | after the account gate | accepted balance | R.16 snapshot | yes | yes | blocks | yes | yes | no | no | ACTIVE_AND_TESTED |
| Portfolio stop-risk | `portfolio_risk_cap_exceeded` | accepted equity | 5% | yes | yes | blocks when the cap cannot be formed | yes | yes | no | no | ACTIVE_AND_TESTED |
| Position sizing | `position_sizing` | accepted equity, price, stop | risk 1% capped at 1% | yes | yes | blocks | yes | yes | no | no | ACTIVE_AND_TESTED |
| Gross notional | enabled branch plus `_pending_gross_usd` | open positions, pending reservations, candidate | `MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV`, default 0 | no | only when the percentage is above zero | blocks `notional_exposure_unreadable` | yes | yes | no | no | IMPLEMENTED_BUT_DISABLED |
| Unit cap | `_configured_unit_cap` | candidate units | `MAX_POSITION_UNITS`, default 0 | no | only when the cap is above zero | non-positive size blocks | yes | yes | no | no | IMPLEMENTED_BUT_DISABLED |
| Exposure holds | reservation and position gates | local books | FILLED, PENDING, PARTIAL, UNRESOLVED | yes | yes | fail closed | yes | yes | in-process books | not proven without PostgreSQL | ACTIVE_AND_TESTED |
| Daily realised loss | `block_reason` | accepted equity and `unrealised` | 2% of the day start | no; `DECISION_REPAIR_ACCOUNT_RISK` is off | only when that flag is on | missing unrealised latches | yes | yes | later read of the JSON file | restart not executed | IMPLEMENTED_BUT_DISABLED |
| Daily total loss | same function | realised plus unrealised | 3% | same flag | same | same | yes | yes | same | restart not executed | IMPLEMENTED_BUT_DISABLED |
| Drawdown | same function | peak versus accepted equity | 5% | same flag | same | first positive equity becomes the peak | yes | yes | same | restart not executed | IMPLEMENTED_BUT_DISABLED |
| Quote structure | `_market_entry_block` | bid and ask | positive, finite, ask at least bid | yes on the shared path | yes | blocks | yes | yes | no | no | ACTIVE_AND_TESTED |
| Numeric spread | evidence `spread_limit` | ask minus bid | none approved | no approved threshold | recorded, not a pass | malformed spread blocks | yes | yes | no | no | PARTIALLY_INTEGRATED |
| Quote age | existing `MANAGE_PRICE_STALE_SEC` of 90 | supplied timestamp | 90 seconds | only when both clocks are supplied | yes | missing timestamp stays `not_evaluated` | yes | yes | no | no | PARTIALLY_INTEGRATED |
| Lookback | `_entry_lookback_requirement` | candle count versus selector lookback | scalp 50, swing 100, otherwise 50 | yes on the shared path | yes | blocks | yes | yes | no | no | ACTIVE_AND_TESTED |
| Margin | evidence only | none | none | no | recorded as not implemented | reported, not converted to a pass | before reservation as evidence | before adapter as evidence | no | no | NOT_IMPLEMENTED |

`current_equity()` remains off the shared entry path.

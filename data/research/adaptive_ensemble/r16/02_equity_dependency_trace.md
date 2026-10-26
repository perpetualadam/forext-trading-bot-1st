# Equity dependency trace

SOURCE-REVIEWED before the repair. The active new-entry decision is `evaluate_one_instrument_iteration`.

## Active entry path

| Check | Equity source before R.16 | Validated | Can change mid-decision | Can fall back | Affects permission or size | Status |
|---|---|---|---|---|---|---|
| `_account_entry_block` | `dependencies.balance`, else payload `equity` | yes | no, once copied | no `current_equity` | blocks entry | active |
| `position_sizing` | accepted snapshot | yes | no | no | size | active |
| `cap_position_units` | none | n/a | n/a | n/a | size only if `MAX_POSITION_UNITS` > 0 | disabled at default 0 |
| gross notional cap | `current_equity()` only when the portfolio percentage is > 0 | no | yes, via process state | yes | permission when enabled | disabled at default 0 |
| `stop_risk_account_ccy` for the candidate | price, stop distance, units | n/a | no | no | the risk amount, not a second equity | active |
| `portfolio_risk_amount` | open-position stops | n/a | if positions change | no | the numerator | active |
| `portfolio_risk_cap_exceeded` | `current_equity()` | no | yes | broker NAV, equity curve, then `Config.BASE_BALANCE` | permission | active defect |
| USD-direction guard | position count | n/a | n/a | n/a | permission | active, not equity |
| daily-loss / drawdown latch | separate module | n/a | n/a | n/a | not called here | disconnected; `DECISION_REPAIR_ACCOUNT_RISK` off |
| margin / leverage | none | n/a | n/a | n/a | not modeled by `position_sizing` | absent |

`current_equity()` in `forex_bot/state.py` returns broker NAV when set, otherwise the last equity-curve point, otherwise `Config.BASE_BALANCE` (default 10000).

## Not an entry permission

- `_maybe_log_performance_metrics`, `daily_report`, and `run_bot` portfolio reporting call `current_equity()`. They do not size or permit an entry. `run_bot` was not executed.
- The legacy tail still sizes from `current_equity()` and reads `last_account_summary()`. It returns at “legacy broker tail is not a dispatch path” and cannot place an order.
- Shadow observation reads `last_account_summary()` and discards the result. It is not the shared entry path.
- `backtest.py` and Telegram reporting are outside this entry path and were not modified.

## Authoritative field

If `dependencies.balance` is present, it is the equity. Payload `equity` is used only when balance is absent. A caller-supplied `verified` flag is not account proof.

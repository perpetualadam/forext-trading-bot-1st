# STAGE R.29 — OFFLINE STRATEGY READINESS REPORT

**Classification: `R29_STRATEGY_SIGNAL_ONLY_VALIDATED`**

Branch `main`, HEAD `d080d897945bc44fa37c02caab504ed707146bec`. The existing dirty tree and R.24–R.28 evidence were left in place. No strategy was activated. No broker, PostgreSQL, or network connection was opened.

## Selected strategy

`scalp` was selected. It has a complete deterministic rule in `signal_from_indicators` and `signal_from_arrays`, the shared evaluate path already accepts it by name, and local EUR_USD M5 candles with bid and ask cover the default lookback of 50. The rule does not call an external service.

The other five were deferred. `trend` and `mean_reversion` use the same indicator family and the same shadow-only status. The three swing names use the longer lookback and are not the default name on the shared path. None of the six has its own live entry, exit, stop, or take-profit. Live direction is still the AI vote plus the RL gate. Selection was not based on expected profit.

All six `Strategy.active` flags and `authorised_for_live` flags remained false.

## Data quality

Local M5 files for AUD_USD, EUR_USD, GBP_USD, USD_CAD, USD_CHF, and USD_JPY each contain about 74,500 rows from 2025-09-01 00:00 UTC through 2026-08-31 23:50 UTC. Timestamps are UTC. There are no duplicate timestamps and no null price fields. Each file has bid and ask OHLC beside an unqualified OHLC. On the first 1,000 EUR_USD rows, `close` matches the bid/ask midpoint within 5e-6. Weekend-scale gaps are present: 73 on EUR_USD M5, and 81 to 116 on the other M5 files.

Matching M1 files cover the same calendar span, about 368,000 to 371,000 rows each, also with bid and ask and no duplicate timestamps. They were inventoried and not replayed. The shared path's stated candle timeframe for this rule is M5.

`data/research/adaptive_ensemble/g3/normalized/` holds a later local M5 extract, 2026-09-01 through 2026-10-09, about 8,100 rows per pair, with bid and ask. It was not mixed into the replay. `data/eurusd_m5_2024_sample.csv` has 450 midpoint-only rows and no bid/ask. It was not used.

## Signal results

The unchanged scalp rule is: buy when the fast average is above the slow average and the close is above the fast average; sell on the opposite strict inequality; otherwise no signal. Lookback stayed 50.

On a synthetic rising fixture the rule returns `BUY` / `scalp_momentum_up`. The same frame returns the same result, including from a second process. A falling fixture returns `SELL`. A flat fixture returns no signal. The first indicator rows, an empty frame, a missing close column, NaN, and infinity return `INSUFFICIENT_DATA`. An unknown name returns no signal. A removed bar does not raise and does not get interpolated. Two calls on one frame return one decision.

On EUR_USD M5 bid prices the replay saw 74,572 bars: 21,122 buy states, 21,360 sell states, 32,066 no-signal bars, and 24 warmup bars. Signals at bars 200, 1,000, and 10,000 matched the same bar computed from only the prefix ending at that bar. These are per-bar states, not separate orders.

`signal_from_indicators` previously accepted a non-finite price that `signal_from_arrays` already rejected. It now rejects non-finite close, averages, ATR, Bollinger bands, high, and low, and non-finite breakout extremes. No parameter or activation setting was changed.

## Risk-gated integration

A validated buy direction was passed into the existing `evaluate_one_instrument_iteration` path with `simulation=True`, an inert fake broker, and `PERSIST_EXEC_ORDERS=0`. The durable strategy flag stayed inactive. The harness dependency allowed the gate to be exercised without writing activation.

Thirteen blocked cases each returned a specific reason, zero broker dispatches, no reservation attempt, and `production_eligible == false`:

| Condition | Reason |
| --- | --- |
| Daily realised loss | `daily_realised_loss_limit` |
| Drawdown at the cap | `max_drawdown_limit` |
| Open notional above the cap | `total_exposure_limit` |
| Stale snapshot | `account_snapshot_stale` |
| Missing account | `account_missing` |
| OANDA summary without NAV | `broker_equity_missing` |
| Transaction pages without bodies | `transaction_pages_incomplete` |
| Non-positive bid | `quote_bid_not_positive` |
| Non-finite stop distance | `sizing_input_invalid` |
| Recovery unreadable | `recovery_unreadable` |
| FILLED exposure | `exposure_unconfirmed` |
| UNRESOLVED intent | `unresolved_intent` |
| Active reservation | `active_reservation` |

One eligible synthetic account reached the inert broker once. A second evaluation of the same symbol, while that harness position remained open, returned `position_already_open` and did not dispatch again. `production_eligible` stayed false.

## Replay and costs

No simulated trades and no P&L were produced. The scalp rule does not define an exit, a holding time, a stop, or a take-profit. Inventing those would invent a performance record.

The median ask-minus-bid on the 42,482 directional bars is 0.00016 price units. That is an observed spread, not a commission, slippage, or financing model. Those costs are not in the files. The spread observation is not evidence that the strategy is profitable.

## Tests and regressions

Focused R.29 tests: 8 passed, 0 failed, 0 skipped, 0 deselected.

| Suite | Result |
| --- | --- |
| R.29 | 8 passed |
| R.27 | 10 passed |
| R.26 | 9 passed |
| R.25 | 10 passed |
| R.4–R.9 | 120 passed, 7 skipped, 1 deselected |
| R.10 | 69 passed, 5 skipped |
| R.11 | 51 passed, 5 skipped |
| R.12 | 118 passed, 5 skipped |
| R.13 | 81 passed, 6 skipped |
| R.14 | 143 passed, 5 skipped |
| R.15 | 165 passed, 6 skipped |
| R.16 | 135 passed, 6 skipped |
| R.17 | 174 passed, 9 skipped |
| R.18 | 203 passed, 9 skipped |
| R.19 | 213 passed, 9 skipped |
| R.20 | 30 passed |
| R.21 | 24 passed |
| R.22 | 20 passed |
| R.23 | 15 passed |
| R.24 | 14 passed |

Every suite exited 0. The previously observed R.10/R.11 `WinError 5` state-file failure did not recur. R.28 has no offline pytest module. Its PostgreSQL scripts were not run, and the isolated database was not started.

## Source change

`forex_bot/shadow/signals.py` gained the non-finite rejection described above. SHA-256 before: `05757587ea79d64bfc9dc35e279de8ab156bbdfcf5344a08199d19326181ec28`. SHA-256 after: `4dc8ce797299e42c200f59e760099a3688ff93f35a1f8ccdfd135ae91b4a7051`. No other application source file was changed.

## Remaining blockers

The live path still takes direction from the AI vote and RL gate, not from this rule. The rule has no exit, stop, take-profit, commission, or financing definition, so a profit figure is not supported. A directional state repeats on consecutive bars and must not be treated as a new order. All six strategies remain inactive and unauthorised for live use. Account financing, fees, transfers, and corrections remain unresolved from R.27. Offline signal validation is not profitability and is not permission to trade.

**PRODUCTION DEPLOYMENT: NO-GO.**

**PRACTICE ORDERS: NOT AUTHORISED.**

**LIVE TRADING: NOT AUTHORISED.**

**ROLLBACK: NO-GO.**

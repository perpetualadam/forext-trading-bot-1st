# STAGE R.30 — SCALP TRADE LIFECYCLE AND COST-AWARE BACKTEST REPORT

**Classification: `R30_COST_AWARE_BACKTEST_COMPLETED`**

Branch `main`, HEAD `d080d897945bc44fa37c02caab504ed707146bec`. Existing changes and R.24–R.29 evidence were left in place. All six `Strategy.active` and `authorised_for_live` flags remained false. No production source file was changed.

The completed backtest lost money in both slices. That is a research result, not a trading authorisation.

## Frozen rules

The specification was written and hashed before the historical run. SHA-256 `d5db0aa73cb9357c01b75cbbdb2224240026b24493109113f29ff4166839e691`. It was not edited after the results.

- A new event is a BUY or SELL whose previous bar is not the same direction. Repeated states do not add size.
- One position. No pyramiding. A reversal exits and does not open the other side on that exit.
- The fill is the next bar's open, and only when that bar is exactly five minutes later, inside 08:00–22:00 UTC, inside the FX week, and outside the Friday 20:45–21:00 UTC flatten window. Otherwise the entry is cancelled.
- Longs enter on the ask and exit on the bid. Shorts enter on the bid and exit on the ask.
- Stop 0.002 and take-profit 0.004 are the source defaults (`SL_FALLBACK_PIPS` 20, `TP_RISK_REWARD` 2, EUR_USD pip 0.0001). ATR stops stay off.
- If the open is already beyond the stop, the fill is the open. If a bar touches both stop and take-profit, the stop is used.
- A gap, a closed market, or the Friday flatten exits at that bar's open. The final bar closes any remainder at the exit-side close.
- Size is 1% of realized cash, starting from a synthetic 10,000 USD. A non-positive stop or a size below 1 cancels the entry.
- These thresholds are existing defaults. They were not tuned, and they are not claimed to be optimal.

## Data and split

`data/historical/EUR_USD_M5.csv`, SHA-256 `3ae3c4d061792353b94b8d2be73684f950362f135d47926d1bc8c11a24791091`.

74,572 rows, 2025-09-01 00:00 UTC through 2026-08-31 23:50 UTC. No duplicate timestamps, no null timestamps, no incomplete rows, and no rejected quotes. 73 gaps are longer than five minutes. The signal uses bid OHLC. Fills use bid and ask. The unqualified close matched the midpoint on the R.29 sample and was not used for fills.

Cleaned count is also 74,572. The split is `floor(0.70 * 74572) = 52200`. In-sample is the first 52,200 bars, through the bar before 2026-05-14 06:20 UTC. Out-of-sample is the remaining 22,372 bars. No in-sample entry was still open at the boundary. The cash ledger is continuous, so the out-of-sample slice starts at about 2,144.70 USD rather than a fresh 10,000.

## Performance

The actual scalp rule produced 21,122 buy states, 21,360 sell states, and 32,090 bars with no direction. Direction changes numbered 11,958. While flat and inside the session, 1,903 entries were scheduled and 1,873 filled. Thirty were cancelled. Prefix checks at bars 200, 1,000, and 10,000 matched the full-sample signal.

Spread-only ledger, with the spread inside the bid/ask fill and no extra slippage:

| | In-sample | Out-of-sample |
| --- | ---: | ---: |
| Trades | 1,291 | 582 |
| Long / short | 650 / 641 | 267 / 315 |
| Bid/ask P&L | −7,855.30 | −976.84 |
| Midpoint reference | −1,990.24 | −122.94 |
| Win rate | 26.1% | 22.7% |
| Average win | 31.98 | 7.97 |
| Average loss | −19.61 | −4.54 |
| Profit factor | 0.58 | 0.52 |
| Max drawdown | 78.7% | 46.0% |
| Consecutive losses | 17 | 20 |
| Average hold | 94.4 minutes | 90.4 minutes |
| Bars in a position | 45.6% | 47.0% |

Ending cash is 1,167.87. Most exits are signal reversals: 1,690 of 1,873. Stops 75, take-profits 59, weekend flattens 36, gap exits 13. The wide 20-pip bracket rarely binds before the next opposite state.

Out-of-sample average win and loss are smaller in dollars because size is 1% of the cash that remains. Win rate and profit factor do not depend on restarting the account, and both stay below a break-even profile.

## Slippage

Extra adverse slippage is hypothetical. It is not subtracted on top of a second spread.

| Extra slippage per side | Ending cash | In-sample profit factor | Out-of-sample profit factor |
| --- | ---: | ---: | ---: |
| 0 | 1,167.87 | 0.58 | 0.52 |
| 0.00005 | 467.70 | 0.47 | 0.39 |
| 0.00010 | 181.39 | 0.39 | 0.31 |

The smaller out-of-sample dollar loss in the one-pip run is the depleted account, not an improvement. Profit factor falls in both slices. Commission, financing, and swap are not in the file and were not set to zero. Overnight holds can carry an unmeasured financing cost. No real-world net profit is claimed. The midpoint reference is also negative in both slices.

## Risk-gated integration

Representative entries were passed through `evaluate_one_instrument_iteration` with an inert broker and `PERSIST_EXEC_ORDERS=0`. The durable strategy flag stayed inactive.

One eligible synthetic buy reached the inert broker once. A repeated evaluation while that harness position was open returned `position_already_open` and did not dispatch again.

Blocked cases, each with `reservation_attempted == false`, `broker_requests == 0`, and `production_eligible == false`:

| Condition | Reason |
| --- | --- |
| Non-finite stop | `sizing_input_invalid` |
| Invalid NAV | `broker_value_nonfinite` |
| Daily realised loss | `daily_realised_loss_limit` |
| Drawdown at the cap | `max_drawdown_limit` |
| Open notional above the cap | `total_exposure_limit` |
| Active reservation | `active_reservation` |
| Unresolved intent | `unresolved_intent` |
| Transaction pages without bodies | `transaction_pages_incomplete` |

Production risk defaults were not changed.

## Tests

Focused R.30 tests: 13 passed, 0 failed, 0 skipped, 0 deselected.

| Suite | Result |
| --- | --- |
| R.30 | 13 passed |
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

Every suite exited 0. `WinError 5` did not recur. R.28 PostgreSQL scripts were not run.

## Source

No production module changed in this stage. `forex_bot/shadow/signals.py` remains SHA-256 `4dc8ce797299e42c200f59e760099a3688ff93f35a1f8ccdfd135ae91b4a7051`. The new research simulator `data/research/adaptive_ensemble/r30/simulator.py` is SHA-256 `fad94aed899f146dd780db29e602801100277f922b2793156edd4926ad14c6cc`. It is not on the live execution path.

## Limitations

OHLC bars do not reveal the intrabar sequence, so a bar that touches both stop and take-profit is filled at the stop. Commission and financing are unknown. The 20-pip, 2R, 1%, and session values were not validated as economic choices. The live bot still takes direction from the AI vote and the RL gate. The six strategies remain inactive. A correct losing backtest is not evidence that the strategy should be traded.

**PRODUCTION DEPLOYMENT: NO-GO.**

**PRACTICE ORDERS: NOT AUTHORISED.**

**LIVE TRADING: NOT AUTHORISED.**

**ROLLBACK: NO-GO.**

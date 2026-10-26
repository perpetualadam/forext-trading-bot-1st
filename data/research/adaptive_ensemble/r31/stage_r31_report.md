# STAGE R.31 — COMPARATIVE OFFLINE STRATEGY SCREENING REPORT

**Classification: `R31_COMPARATIVE_SCREENING_COMPLETED`**

Branch `main`, HEAD `d080d897945bc44fa37c02caab504ed707146bec`. The existing dirty working tree and the R.24–R.30 evidence were left in place. All six `Strategy.active` and `authorised_for_live` flags remained false. R.31 changed no production source file. The R.30 simulator was not modified.

This screen lost money for every strategy on bid/ask fills in both slices. Completion records that the comparison was run. It does not authorise a strategy, and it does not select one for a later study.

## Simulator review

Reviewed before any candidate run. File `data/research/adaptive_ensemble/r30/simulator.py`, SHA-256 `fad94aed899f146dd780db29e602801100277f922b2793156edd4926ad14c6cc`. The review is `simulator_review.md`, SHA-256 `6d4b0b2cadb5f372cafdfc933d534a9668372aab1164dcbf5b0a0e28c9823975`.

The critical execution assumptions held:

- A signal at bar T fills at the next bar's open, and only when that bar exists.
- A long enters on the ask and exits on the bid. A short enters on the bid and exits on the ask.
- An opposite signal exits at the next open and does not open the other side on that bar.
- Friday flatten, a closed FX week, and a bar that is not exactly five minutes later exit at the exit-side open. A gap worse than the stop fills at the open.
- A bar that touches both stop and take-profit fills at the stop.
- After the entry open, that same bar's high and low can reach the bracket. That matches the frozen rule that the bracket is tested on the bar after the entry open.
- Repeated same-direction states do not open another trade. Size is 1% of realised cash divided by the 0.002 stop. Open profit is not used for the next size.
- Signals are an input. The historical driver builds them with `signal_from_arrays`.

Holds may remain after 22:00 UTC, because the frozen rule blocks new entries outside the session and does not add a 22:00 exit. A weekend jump that also falls in the flatten window is labelled `gap_exit`; the fill is still the next open. `signal_from_arrays` treats infinity as finite because its check uses `isnan` only. The EUR_USD file has no non-finite quotes, so that helper was left unchanged.

No material execution defect was found. The published R.30 scalp figures stay the baseline. There is no revised-result column.

The scalp rerun on the same file produced 1,873 spread-only trades and ending cash `1167.866984`, matching the published R.30 trade count and ending cash within `1e-6`.

## Frozen protocol

`01_comparison_protocol.md` was written and hashed at 2026-10-20T00:48:00+01:00, before the candidate run. SHA-256 `6ca23bac5be4e5705bc5b761b23ed16880fb1b554491a0e5774c629abfdadc88`. `spec_freeze.json` recorded `performance_measured: false`. The runner refused to continue if that hash differed, if performance had already been marked, or if the simulator hash differed from the R.30 hash. The protocol file was not edited after the results.

The common lifecycle is the R.30 simulator: next-bar bid/ask fills, stop 0.002, take-profit 0.004, no ATR stop, one position, continuous cash from a synthetic 10,000 USD, session 08:00–22:00 UTC, FX week closed Friday 21:00 UTC through Sunday 21:00 UTC, Friday flatten 20:45–21:00 UTC. Extra slippage of 0, 0.00005, and 0.00010 per side is reported. Commission, financing, and swap are not estimated and are not treated as zero.

The ranking instrument is EUR_USD M5 only. The other five M5 pairs, the M1 files, and the later `g3/normalized` extract were excluded before the results because they are a different instrument, a different timeframe, or a later extract.

A candidate merits a later independent validation study only if every line below is true on the spread-only ledger, plus the slippage line:

1. At least 100 closed trades in each slice.
2. P&L greater than zero in each slice.
3. Profit factor greater than 1 in each slice.
4. Maximum drawdown fraction strictly below 0.25 in each slice.
5. At 0.00005 extra slippage per side, out-of-sample P&L greater than zero and out-of-sample profit factor greater than 1.

A smaller loss than scalp is a failure. The R.30 out-of-sample window is the same period already examined in R.30. It is research screening evidence for every name in this report. It is not a fresh holdout for a name chosen here.

## Strategies

All six existing rules are compatible with bid OHLC M5 through `signal_from_arrays`. None was excluded.

| Strategy | Role | Lookback | Source of the lookback |
| --- | --- | ---: | --- |
| scalp | baseline | 50 | `SCALP_LOOKBACK` |
| trend | candidate | 50 | scalp family via `lookback_for` |
| mean_reversion | candidate | 50 | scalp family via `lookback_for` |
| swing_trend | candidate | 100 | `SWING_LOOKBACK` |
| swing_mean_reversion | candidate | 100 | `SWING_LOOKBACK` |
| swing_breakout | candidate | 100 | `SWING_LOOKBACK` |

`trend` and `mean_reversion` use the scalp-family lookback in the shadow signal path. On the shared `evaluate` path, with no selector lookback supplied, those two names use `DEFAULT_INDICATOR_LOOKBACK` because the name does not contain `scalp` and does not start with `swing`. Under the offline stub both defaults are 50, so the screen and the gate used the same bar count. Swing names require 100 bars on that path. A 50-bar swing call is rejected as `insufficient_lookback` before any reservation.

## Data

Used file: `data/historical/EUR_USD_M5.csv`.

- SHA-256 `3ae3c4d061792353b94b8d2be73684f950362f135d47926d1bc8c11a24791091`
- EUR_USD, M5, bid and ask present
- 74,572 rows, 2025-09-01 00:00 UTC through 2026-08-31 23:50 UTC
- Duplicate timestamps 0, missing timestamps 0, incomplete rows 0, rejected quotes 0
- 73 gaps longer than five minutes, including the weekend gaps

The split is `floor(0.70 * 74572) = 52200`. In-sample is the first 52,200 bars. Out-of-sample starts at 2026-05-14 06:20 UTC and contains the remaining 22,372 bars. The cash ledger is continuous. Out-of-sample dollar P&L is whatever remains after the in-sample loss. It is not a restarted 10,000 USD account.

The other local M5 files were hashed and not used:

| File | SHA-256 |
| --- | --- |
| `AUD_USD_M5.csv` | `e639a1f817e4b91973ccfea0ee0c8c3dd5279c722ea665c531ad309b359165e0` |
| `GBP_USD_M5.csv` | `ac3ddba51b75f493a08a5ea57e9926e38a5a85b06797de53803e6cd4f8b00d58` |
| `USD_CAD_M5.csv` | `a88eb2c440691bd5893a8317b64e6beaf87bb6f3c93b0c6e6a4cd16e53aa9c60` |
| `USD_CHF_M5.csv` | `3901a2d50a63ef5ca4d10858145cca7fd70d20d24420761e1b7d2d09f2a127bc` |
| `USD_JPY_M5.csv` | `e1b0d3491f873723967315d74e3bd5b707474814a294be4ed50a26e1b8c9805c` |

M1 files and `data/research/adaptive_ensemble/g3/normalized/` were not read for this ranking.

## Comparative performance

Every strategy was run on the same 74,572 bars with its own existing rule. A prefix of 5,001 bars reproduced the signal at bar 5,000 for all six names. Spread-only simulation was repeated and matched. Exact floats are in `performance.json`. Trade rows are in `trades_<strategy>.csv`.

Signal states and entries, spread-only:

| Strategy | BUY | SELL | No direction | Entry events | Scheduled | Filled | Cancelled |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| scalp | 21,122 | 21,360 | 32,090 | 11,958 | 1,903 | 1,873 | 30 |
| trend | 21,268 | 21,515 | 31,789 | 11,947 | 1,902 | 1,872 | 30 |
| mean_reversion | 4,307 | 4,052 | 66,213 | 3,972 | 903 | 880 | 23 |
| swing_trend | 20,971 | 21,401 | 32,200 | 7,877 | 1,173 | 1,150 | 23 |
| swing_mean_reversion | 4,994 | 4,955 | 64,623 | 3,195 | 668 | 654 | 14 |
| swing_breakout | 4,391 | 4,473 | 65,708 | 5,886 | 1,030 | 996 | 34 |

No strategy produced zero trades.

Spread-only in-sample:

| Strategy | Trades | Long / short | P&L | Midpoint P&L | Win rate | Profit factor | Max drawdown | Avg hold (s) | Consecutive losses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| scalp | 1,291 | 650 / 641 | −7,855.30 | −1,990.24 | 0.261 | 0.578 | 0.787 | 5,666 | 17 |
| trend | 1,290 | 650 / 640 | −7,805.67 | −1,895.81 | 0.263 | 0.582 | 0.782 | 5,677 | 17 |
| mean_reversion | 616 | 307 / 309 | −2,848.20 | +856.82 | 0.541 | 0.834 | 0.367 | 11,044 | 6 |
| swing_trend | 807 | 404 / 403 | −6,550.12 | −2,727.72 | 0.258 | 0.605 | 0.659 | 9,906 | 27 |
| swing_mean_reversion | 469 | 235 / 234 | −2,352.11 | +347.61 | 0.501 | 0.864 | 0.338 | 16,245 | 9 |
| swing_breakout | 710 | 365 / 345 | −7,169.99 | −3,941.45 | 0.266 | 0.545 | 0.718 | 10,518 | 21 |

Spread-only out-of-sample, on the continuous depleted ledger:

| Strategy | Trades | Long / short | P&L | Midpoint P&L | Win rate | Profit factor | Max drawdown | Avg hold (s) | Consecutive losses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| scalp | 582 | 267 / 315 | −976.84 | −122.94 | 0.227 | 0.519 | 0.460 | 5,422 | 20 |
| trend | 582 | 268 / 314 | −995.83 | −118.92 | 0.227 | 0.522 | 0.459 | 5,412 | 20 |
| mean_reversion | 264 | 148 / 116 | −989.07 | +558.99 | 0.576 | 0.810 | 0.184 | 11,707 | 6 |
| swing_trend | 343 | 169 / 174 | −976.62 | −65.96 | 0.271 | 0.662 | 0.314 | 10,192 | 11 |
| swing_mean_reversion | 185 | 108 / 77 | −1,006.46 | +69.33 | 0.497 | 0.798 | 0.204 | 15,498 | 6 |
| swing_breakout | 286 | 130 / 156 | −782.05 | −184.39 | 0.294 | 0.624 | 0.292 | 11,451 | 12 |

Ending cash after the whole spread-only sample: scalp 1,167.87, trend 1,198.50, mean_reversion 6,162.73, swing_trend 2,473.26, swing_mean_reversion 6,641.43, swing_breakout 2,047.97. Each started at 10,000.

Exit reasons, in-sample then out-of-sample:

| Strategy | Signal reversal | Stop | Take-profit | Weekend flatten | Gap |
| --- | ---: | ---: | ---: | ---: | ---: |
| scalp | 1,147 / 543 | 65 / 10 | 49 / 10 | 25 / 11 | 5 / 8 |
| trend | 1,147 / 543 | 65 / 10 | 48 / 10 | 25 / 11 | 5 / 8 |
| mean_reversion | 383 / 181 | 196 / 63 | 6 / 4 | 27 / 10 | 4 / 6 |
| swing_trend | 617 / 291 | 98 / 18 | 60 / 15 | 28 / 8 | 4 / 11 |
| swing_mean_reversion | 233 / 104 | 195 / 61 | 18 / 4 | 18 / 9 | 4 / 7 |
| swing_breakout | 523 / 238 | 108 / 15 | 48 / 12 | 27 / 13 | 4 / 7 |

`swing_mean_reversion` also has one in-sample `take_profit_gap`. `swing_breakout` has one out-of-sample `stop_gap`. The gap column above is `gap_exit` only.

## Slippage and spread

The midpoint column is the same trades marked without the bid/ask spread. For `mean_reversion` and `swing_mean_reversion` that reference is positive in both slices. The bid/ask result is negative in both slices. The spread is large enough to remove that reference edge. Trend-family and breakout midpoint results are also negative.

Extra adverse slippage lowers profit factor for every strategy. Ending cash:

| Strategy | Spread only | +0.00005 / side | +0.00010 / side |
| --- | ---: | ---: | ---: |
| scalp | 1,167.87 | 467.70 | 181.39 |
| trend | 1,198.50 | 480.10 | 186.25 |
| mean_reversion | 6,162.73 | 3,989.05 | 2,452.44 |
| swing_trend | 2,473.26 | 1,364.05 | 742.74 |
| swing_mean_reversion | 6,641.43 | 4,608.94 | 3,261.91 |
| swing_breakout | 2,047.97 | 1,175.50 | 744.80 |

Out-of-sample profit factor at those three slippage levels:

| Strategy | 0 | 0.00005 | 0.00010 |
| --- | ---: | ---: | ---: |
| scalp | 0.519 | 0.393 | 0.307 |
| trend | 0.522 | 0.395 | 0.310 |
| mean_reversion | 0.810 | 0.665 | 0.547 |
| swing_trend | 0.662 | 0.536 | 0.441 |
| swing_mean_reversion | 0.798 | 0.667 | 0.580 |
| swing_breakout | 0.624 | 0.521 | 0.435 |

Out-of-sample dollar losses can look smaller at the higher slippage because the continuous account is already depleted. The profit factor is the comparison that stays on the same scale, and it falls. Commission, financing, and swap remain unestimated.

## Screening result

Every strategy had more than 100 closed trades in each slice. Every strategy failed the economic lines. `validation_order` is empty.

| Strategy | Failed lines |
| --- | --- |
| scalp | Both-slice P&L, both-slice profit factor, both-slice drawdown, half-pip out-of-sample |
| trend | Both-slice P&L, both-slice profit factor, both-slice drawdown, half-pip out-of-sample |
| mean_reversion | Both-slice P&L, both-slice profit factor, in-sample drawdown 0.367, half-pip out-of-sample. Out-of-sample drawdown 0.184 is the one economic line that cleared. |
| swing_trend | Both-slice P&L, both-slice profit factor, both-slice drawdown, half-pip out-of-sample |
| swing_mean_reversion | Both-slice P&L, both-slice profit factor, in-sample drawdown 0.338, half-pip out-of-sample. Out-of-sample drawdown 0.204 is the one economic line that cleared. |
| swing_breakout | Both-slice P&L, both-slice profit factor, both-slice drawdown, half-pip out-of-sample |

`trend` ended with slightly more cash than `scalp`. That is still a loss in both slices, with profit factor below 1 and drawdown above 0.25. The frozen gate rejects it. No fragments were combined, and no threshold was changed after the results.

No candidate merits a later independent validation study.

## Risk-gated integration

Each candidate direction was passed through `evaluate_one_instrument_iteration` with synthetic account data, an inert broker, isolated synthetic state, and `PERSIST_EXEC_ORDERS=0`. `production_eligible` stayed false on every call, including the one eligible dispatch. The durable activation flags stayed false. The live AI vote, RL gate, and production order path were not changed.

For each of the five candidates:

- One eligible direction dispatched once (`broker_requests == 1`).
- A second call with the same open position returned `position_already_open` and did not add a broker request.
- Swing names with only 50 bars returned `insufficient_lookback`.
- Invalid stop distance returned `sizing_input_invalid`.
- Missing NAV returned `broker_value_nonfinite`.
- Daily loss, drawdown, and total exposure returned `daily_realised_loss_limit`, `max_drawdown_limit`, and `total_exposure_limit`.
- An active reservation returned `active_reservation`.
- An unresolved intent returned `unresolved_intent`.
- Incomplete transaction pages returned `transaction_pages_incomplete`.

Each blocked case had that specific reason, `reservation_attempted == false`, `broker_requests == 0`, and `production_eligible == false`.

## Tests and regressions

Focused R.31 tests in `tests/test_r31_strategy_screening.py`: 7 passed, 0 failed, 0 skipped, 0 deselected. They cover cash arithmetic, Friday flatten, entry-bar stop and take-profit, short reversal on the ask, deterministic causal signals, the ranking gate, and the risk-gated rejections above.

Offline regressions, all exit 0. `WinError 5` did not recur. R.28 PostgreSQL scripts were not run, and PostgreSQL was not started.

| Suite | Result |
| --- | --- |
| R.31 | 7 passed |
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

The R.4–R.9 deselection is the existing `test_h39_h40_restart_keeps_live_orders_blocked` filter. Exit codes are in `pytest_isolation_log.txt`.

## Research-code hashes

No production file was edited for this stage. `forex_bot/shadow/signals.py` remains the R.29 hash `4dc8ce797299e42c200f59e760099a3688ff93f35a1f8ccdfd135ae91b4a7051`.

| File | SHA-256 |
| --- | --- |
| `r30/simulator.py` | `fad94aed899f146dd780db29e602801100277f922b2793156edd4926ad14c6cc` |
| `r31/01_comparison_protocol.md` | `6ca23bac5be4e5705bc5b761b23ed16880fb1b554491a0e5774c629abfdadc88` |
| `r31/simulator_review.md` | `6d4b0b2cadb5f372cafdfc933d534a9668372aab1164dcbf5b0a0e28c9823975` |
| `r31/ranking.py` | `8e8741592f6b315a7fa3205c4a8d55f2af7c0d12c270268f6b942796528e9d7f` |
| `r31/02_run_comparison.py` | `c855419a3e728258e86b02b742a5d45658d34b51a667bf5bbba9f43e4238f472` |
| `r31/20_run_offline_tests.py` | `51595c3453fc81bc229b9c9d36293d1141c40313165f8b72d710b008bf3bde64` |
| `tests/test_r31_strategy_screening.py` | `271e3d39ebfec3b666219afec7f6b7ad56642d6b419436edfac6d95c9d46ab2e` |

## Remaining limitations

- One instrument and one timeframe. Other local pairs and the later extract were not part of the ranking.
- The out-of-sample window was already used in R.30. A pass on this screen would still have needed a later study. There was no pass.
- Commission, financing, and swap are unknown. Adding them would be a further cost, and the bid/ask result is already negative.
- `trend` and `mean_reversion` follow `DEFAULT_INDICATOR_LOOKBACK` on the shared evaluate path when no selector lookback is supplied. The screen used the shadow family lookback. Both are 50 under the offline stub.
- Holds can remain open after 22:00 UTC under the frozen session rule.
- No strategy is active, and none is authorised for live or practice orders.

**PRODUCTION DEPLOYMENT: NO-GO.**

**PRACTICE ORDERS: NOT AUTHORISED.**

**LIVE TRADING: NOT AUTHORISED.**

**ROLLBACK: NO-GO.**

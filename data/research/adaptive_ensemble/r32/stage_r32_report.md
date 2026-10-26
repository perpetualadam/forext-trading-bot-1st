# STAGE R.32 — TRADING-COST ATTRIBUTION AND SIGNAL EDGE DIAGNOSTICS REPORT

**Classification: `R32_SIGNAL_EDGE_DIAGNOSTICS_COMPLETED`**

Branch `main`, HEAD `d080d897945bc44fa37c02caab504ed707146bec`. The dirty working tree and the R.24–R.31 evidence were left in place. All six `Strategy.active` and `authorised_for_live` flags remained false. The R.30 simulator and both mean-reversion rules were not modified.

`mean_reversion`: **`STOP_RESEARCH`**.

`swing_mean_reversion`: **`INCONCLUSIVE`**.

Neither label carries the current configuration forward. This diagnosis does not authorise trading.

## Frozen protocol

`01_diagnostic_protocol.md` was hashed at 2026-10-20T02:21:00+01:00, before these measurements. SHA-256 `451c70be681468ff00764517a681f885c4d46ee74099b0a517d2641d4b4a28f0`. The runner stopped when that hash differed or when diagnostics were already marked. The file was not edited after the results.

The trade population is the R.31 spread-only ledger. The signal population is the recomputed direction-change events. Forward horizons are 1, 6, 12, and 48 M5 bars. The decision uses the non-overlapping 12-bar mean only. Baselines are a 200-draw label permutation, a 200-draw fair coin, and an always-long / always-short reference, with the seeds in the protocol. Uncertainty is a 400-draw block bootstrap with blocks of 20 events. Stability uses four calendar windows fixed in the protocol.

Input hashes matched the R.30/R.31 records:

| Input | SHA-256 |
| --- | --- |
| `r30/simulator.py` | `fad94aed899f146dd780db29e602801100277f922b2793156edd4926ad14c6cc` |
| `r31/01_comparison_protocol.md` | `6ca23bac5be4e5705bc5b761b23ed16880fb1b554491a0e5774c629abfdadc88` |
| `data/historical/EUR_USD_M5.csv` | `3ae3c4d061792353b94b8d2be73684f950362f135d47926d1bc8c11a24791091` |
| `forex_bot/shadow/signals.py` | `4dc8ce797299e42c200f59e760099a3688ff93f35a1f8ccdfd135ae91b4a7051` |
| `r31/performance.json` | `4ffe74a270f38cdce7de2f566056e6e285608c50e3eef5d004578a38ac196eb9` |
| `r31/trades_mean_reversion.csv` | `06d78203f68f55d8b40146e0c5ecb15ee3130eabb6d6ffabd908ff833fca363c` |
| `r31/trades_swing_mean_reversion.csv` | `c0c2d8e3a62f45e1e5cf8b957db021cb56070dd7546e47a3ec7775efa3c3ab09` |

The EUR_USD M5 file is the same 74,572-row bid/ask sample used in R.31, split at bar 52,200. Recomputed signal counts matched R.31: `mean_reversion` 4,307 BUY, 4,052 SELL, 3,972 entry events; `swing_mean_reversion` 4,994 BUY, 4,955 SELL, 3,195 entry events.

## P&L reconciliation

Every spread-only trade rebuilt `pnl` and `mid_pnl` from its prices and units. The largest per-trade gap was inside `1e-6` USD. The largest spread residual was about `3e-14` USD. In-sample, out-of-sample, whole-sample, and ending-cash totals matched `performance.json` within `1e-4` USD. Row counts matched: 880 and 654.

`pnl = mid_pnl + execution difference`. The spread is the execution difference. It is not subtracted again.

| Strategy | Price-movement P&L | Bid/ask execution difference | Quoted P&L |
| --- | ---: | ---: | ---: |
| mean_reversion | +1,415.81 | −5,253.08 | −3,837.27 |
| swing_mean_reversion | +416.93 | −3,775.50 | −3,358.57 |

Per closed trade, the midpoint ledger averages +1.61 USD and +0.64 USD. The quoted ledger averages −4.36 USD and −5.14 USD. The difference is the bid/ask execution cost, about 5.97 USD and 5.77 USD per trade.

Quote exits account for the entry half-spread plus the exit half-spread. Order-price exits (`stop`, `take_profit`, `ambiguous_stop`) account for the entry half-spread only, because the simulator stores the order price as the exit reference. Those trades number 269 and 278. Their exit spread is unmeasured, not zero. No hold contained an unobserved bar inside the measured path. Gap exits remain 10 and 11, plus one `take_profit_gap`, and those fills stay at the open.

The published half-pip scenario adds a further −2,173.69 USD and −2,032.50 USD. The one-pip scenario adds −3,710.29 USD and −3,379.52 USD. Those amounts are hypothetical extra slippage. They are outside the spread-only split above. Commission, financing, and swap were not estimated.

## What the loss is made of

Both current configurations lose because a small favourable midpoint move is smaller than the bid/ask cost of the round trip. The association and the cost show up together in the same trades.

On the signal sample, the pre-registered 12-bar direction-adjusted midpoint mean is 0.393 pips for `mean_reversion` and 0.375 pips for `swing_mean_reversion`. The median full spread on those same bars is 1.600 pips. A round trip on this file costs about one full spread. The expected one-hour move is about one quarter of that cost.

The closed-trade midpoint result is the same size: about 0.42 pips and 0.16 pips per unit. Median holding time is 155 minutes and 220 minutes, so the lifecycle holds longer than the one-hour diagnostic and still realises well under one pip. Median favourable excursion is 6.90 pips and 8.60 pips. Median adverse excursion is 10.90 pips and 14.70 pips. Adverse excursion exceeds favourable excursion on 61.8% and 60.6% of trades. A favourable extreme above the entry spread appears on 77.5% and 82.1% of trades, and that extreme is not evidence that the spread could have been taken before the adverse move. Stop and take-profit bars have an unknown intrabar order.

Signal reversals are 564 of 880 exits and 337 of 654 exits. Take-profit exits are 10 and 22. The book turns over about 16.6 and 12.3 trades per ISO week across 53 weeks. Each week pays the spread many times to chase a sub-pip expected move.

The break-even extra price on the midpoint mean is 0.42 pips and 0.16 pips. The quoted spread is already larger than both, so there is no remaining cost budget. Added slippage makes the quoted loss larger.

## Predictive information

The 12-bar sample excludes overlapping windows. `mean_reversion` keeps 2,479 of 3,972 events. `swing_mean_reversion` keeps 1,904 of 3,195. Every kept 12-bar window is a uniform five-minute path. Fifty-eight and thirty-three events have no exact 12-bar horizon and are omitted.

| | mean_reversion | swing_mean_reversion |
| --- | ---: | ---: |
| Non-overlapping mean | +0.393 pips | +0.375 pips |
| Median | +0.300 pips | +0.300 pips |
| Positive frequency | 52.2% | 52.4% |
| Effect size, mean / standard deviation | 0.044 | 0.039 |
| BUY mean | +0.604 pips (1,265) | +0.604 pips (963) |
| SELL mean | +0.173 pips (1,214) | +0.141 pips (941) |
| Always-BUY mean at the same times | +0.224 pips | +0.236 pips |
| Block-bootstrap 2.5–97.5 percentile | +0.050 to +0.726 pips | −0.046 to +0.731 pips |
| Shuffle 95th percentile | +0.278 pips | +0.351 pips |
| Coin-toss 95th percentile | +0.293 pips | +0.364 pips |

The overlapping 12-bar means have the same sign: +0.379 pips and +0.342 pips. The other frozen horizons are also positive. Their non-overlapping means run from 0.133 pips at one bar to 1.496 pips at 48 bars for `mean_reversion`, and from 0.134 pips to 0.799 pips for `swing_mean_reversion`. None of those four means exceeds the 1.600 pip median spread. The decision horizon stays at 12 bars.

`mean_reversion` clears the interval, both null percentiles, and all four calendar windows. The standardized effect is 0.044. A sample of this length can put a very small mean above zero. That is a detectable midpoint association. It is also smaller than the spread, which is why the frozen rule stops it.

`swing_mean_reversion` has a similar point estimate. Its block-bootstrap interval includes zero, so the protocol does not treat the association as resolved. The point estimate also sits below the spread. The interval check is the rule that fired.

BUY means are larger than SELL means. The decision uses the pooled sample. The stronger side was not split out into a new rule.

## Time stability

All four pre-registered windows have more than 30 non-overlapping events, and every window mean is positive.

| Window | mean_reversion | swing_mean_reversion |
| --- | ---: | ---: |
| 2025-09 through 2025-11 | +0.232 pips (615) | +0.207 pips (460) |
| 2025-12 through 2026-02 | +0.256 pips (620) | +0.650 pips (486) |
| 2026-03 through 2026-05 | +0.577 pips (625) | +0.541 pips (462) |
| 2026-06 through 2026-08 | +0.502 pips (619) | +0.106 pips (496) |

The sign is stable. The size stays below one pip in every window. The R.30/R.31 sample was already examined, so these windows are a stability description inside a used sample. They are not a new holdout. Two strategies and four descriptive horizons were inspected. The gate itself uses one pre-registered horizon per strategy. This report does not add a family-wise significance claim on top of that gate.

## Research decision

`mean_reversion` is `STOP_RESEARCH`. The 12-bar mean is positive, its bootstrap interval lies above zero, it exceeds both null 95th percentiles, and all four windows agree in sign. The mean is 0.393 pips against a 1.600 pip median spread, so the remaining-gate rule stops the current configuration.

`swing_mean_reversion` is `INCONCLUSIVE`. The bootstrap interval includes zero. The protocol ends the current configuration there and does not open another study to break the tie.

No parameter, band, lookback, stop, or exit was changed.

## Tests and regressions

Focused R.32 tests: 10 passed, 0 failed, 0 skipped, 0 deselected. They cover attribution, the flat-market long/short cost, direction-adjusted returns, gapped horizons, non-overlapping windows, reproducible seeds, calendar windows, the bootstrap length check, the decision order, and excursion handling.

| Suite | Result |
| --- | --- |
| R.32 | 10 passed |
| R.31 | 7 passed |
| R.30 | 13 passed |
| R.29 | 8 passed |
| R.27 | 10 passed |
| R.26 | 9 passed |
| R.25 | 10 passed |
| R.4–R.9 | 120 passed, 7 skipped, 1 deselected |
| R.10 first run | 1 failed, 68 passed, 5 skipped |
| R.10 retry | 69 passed, 5 skipped |
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

The R.10 failure was `test_i24_reconciliation_unavailable`. Windows returned `WinError 5` while replacing `data/research/adaptive_ensemble/r10/synthetic_live_safety_state.json`. `live_safety.py` was not changed and the file was not deleted. The same suite then passed. The first failure is recorded in `pytest_isolation_log.txt` and `pytest_r10_attempts.txt`. R.28 database scripts were not run.

## Research-code hashes

| File | SHA-256 |
| --- | --- |
| `r32/01_diagnostic_protocol.md` | `451c70be681468ff00764517a681f885c4d46ee74099b0a517d2641d4b4a28f0` |
| `r32/diagnostics.py` | `ca6a0db1f38a940e139e93a9019beca1775b1c2a48bd270655c9801be5b5ae6a` |
| `r32/02_run_diagnostics.py` | `f6cb3a824a7cf29d76527e5d8a4340c2e3096270b0a2ef843c1e0218a59cc6f3` |
| `r32/20_run_offline_tests.py` | `8ee8a9dfeabad52a6e03cc6d64f7a3218d15c54cf1b57d6cb334c8f43de10e0e` |
| `tests/test_r32_signal_diagnostics.py` | `da9b38d011d9d9439dcd756f20b4dc8a7d1d178feef2906a7c57bc499914b697` |

## Limitations

- One instrument and one timeframe. The later local extract was not used.
- The sample was already used in R.30 and R.31. A small detected mean is still an in-sample description.
- Block bootstrap treats blocks of 20 non-overlapping events as exchangeable. That is an approximation.
- Order-price exits do not have an observed exit spread.
- Commission, financing, and swap remain unknown.
- Favourable and adverse extremes on a stop or target bar have no known order.
- The 48-bar descriptive mean was not allowed to replace the 12-bar decision.

**PRODUCTION DEPLOYMENT: NO-GO.**

**PRACTICE ORDERS: NOT AUTHORISED.**

**LIVE TRADING: NOT AUTHORISED.**

**ROLLBACK: NO-GO.**

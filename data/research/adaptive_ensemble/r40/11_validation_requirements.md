# R.40 independent validation requirements

The September 2025–August 2026 M5 year has been used by R.29 through R.39. It is research-exposed. A new label computed on that year can check causality and data quality. It cannot be the independent test of a rule that was kept because it looked good there.

The local files end on 2026-08-31. There is no later untouched sample on disk. A few recent weeks inside this file would be a thin slice of the same exposed year. Two weeks contain on the order of fifty complete H4 candles before weekend removal, and far fewer independent swing events. That is not a validation sample.

## Minimum fresh coverage

A later performance test needs new bid/ask M5 data that does not overlap this year, with the same columns and the same complete-candle rule. The fresh span needs to be long enough to contain more than one market regime and more than one instrument. A practical minimum is a further contiguous year, or a shorter span only if it still contains at least 100 pre-registered independent structure events per instrument after embargo. One hundred events is a floor for counting a test, not a guarantee that the test is powerful. Correlated USD pairs do not each contribute a fresh 100. R.38's EUR_USD and GBP_USD association near 0.79 is the reason to treat the six as one portfolio with a dependence adjustment.

If that data is not already stored, the choices are to wait, or to authorise a separate data-acquisition stage. R.40 does not acquire it.

## Protocol that a later evaluation would have to freeze first

- Feature definitions, `k`, touch and break buffers, and holding rules are written down before the fresh data is scored.
- Thresholds are not chosen on the test slice.
- Training, validation, and test are chronological. The purge and embargo are at least the swing confirmation delay plus the maximum holding period. For `k = 2` on H4 that confirmation delay is eight hours, and the embargo grows with the hold.
- Uncertainty uses a block bootstrap or another dependence-aware method. The block covers the hold and overlapping swings.
- Multiple rules or multiple pairs require a pre-registered multiplicity adjustment.
- Execution uses bid for a sell and ask for a buy, on completed candles, with an explicit financing assumption. If financing is unknown, the result stays incomplete rather than omitting the cost.
- Portfolio exposure counts simultaneous positions in correlated pairs.
- The opportunity count is the number of non-overlapping decisions after embargo, not the number of M5 rows.

## When to stop

Stop the research line when the pre-registered confirmatory test has a cost-adjusted mean at or below zero, when its dependence-aware interval includes zero or below, when the fresh event count is under the floor, or when the only positive slice appears after a threshold was changed. A pass on one pair, or on a handful of weeks, does not cancel a failed confirmatory test.

R.36 through R.39 already failed their own frozen economic tests. Those failures stay in force. A higher-timeframe definition does not reopen them.

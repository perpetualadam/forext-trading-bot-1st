# R.31 frozen comparison protocol

Frozen at 2026-10-20T00:48:00+01:00, before any candidate performance measurement.

This is a research screen. It does not activate a strategy and it does not treat the R.30 out-of-sample window as a fresh holdout for a strategy chosen here.

## Candidates and baseline

Eligible, because each returns BUY, SELL, or no direction from bid OHLC through `signal_from_arrays`:

| Strategy | Family lookback | Source default |
| --- | ---: | --- |
| scalp | 50 | `SCALP_LOOKBACK` |
| trend | 50 | `SCALP_LOOKBACK` |
| mean_reversion | 50 | `SCALP_LOOKBACK` |
| swing_trend | 100 | `SWING_LOOKBACK` |
| swing_mean_reversion | 100 | `SWING_LOOKBACK` |
| swing_breakout | 100 | `SWING_LOOKBACK` |

`scalp` is the baseline. It is rerun only to confirm the unchanged simulator still matches the R.30 trade count and spread-only P&L. The published R.30 figures are not replaced unless that check fails.

No candidate is excluded for incompatibility. M1 files, the other five M5 pairs, and the later `g3/normalized` extract are not inputs. They are a different timeframe, a different instrument, or a later extract. Choosing among them after seeing returns is not allowed. One instrument and one timeframe are fixed below.

## Data

- File: `data/historical/EUR_USD_M5.csv`
- Instrument and timeframe: EUR_USD, M5
- Signal prices: bid open, high, low, close
- The chronological split is the R.30 rule: in-sample is the first `floor(0.70 * cleaned_rows)` bars. The remainder is out-of-sample.
- The same cleaned bars and the same split are used for every strategy.

## Lifecycle

The R.30 simulator is the common engine. Its rules are not refitted:

- New entry only when the direction differs from the previous bar, the book is flat, the signal bar is inside 08:00–22:00 UTC on an open FX weekday, and it is outside Friday 20:45–21:00 UTC.
- Fill at the next bar's open. Cancel the entry if that bar is not exactly five minutes later or is outside the session.
- Long ask entry and bid exit. Short bid entry and ask exit.
- Stop distance 0.002. Take-profit distance 0.004. No ATR stop.
- Opposite signal exits at the next open and does not reverse into a new position on that bar.
- Gap, market-closed, and Friday-flatten exits use the next open. A worse gap does not fill at the original stop.
- A bar touching both stop and take-profit fills at the stop.
- One position. No pyramiding.
- Starting cash 10,000 USD. Size is 1% of realised cash divided by 0.002. Size below 1 or a non-positive stop cancels the entry.
- The ledger is continuous. Out-of-sample dollar results keep whatever cash remains. They are not a restarted 10,000 account.

## Costs

- Primary result: bid/ask fills, extra slippage 0. Spread is not subtracted again.
- The midpoint P&L on those same trades is the spread reference.
- Extra adverse slippage of 0.00005 and 0.00010 per side is reported separately.
- Commission, financing, and swap are not estimated and are not treated as zero.

## Screening gate

A candidate merits a later independent validation study only if every line below is true. Otherwise it is rejected. Being less unprofitable than scalp is not a pass.

1. At least 100 closed trades in-sample and 100 out-of-sample, spread-only.
2. Spread-only P&L greater than zero in both slices.
3. Spread-only profit factor greater than 1 in both slices. If there are wins and no losses, the missing profit factor counts as greater than 1. If there are no wins, it does not.
4. Spread-only maximum drawdown fraction strictly below 0.25 in both slices.
5. At 0.00005 extra slippage per side, out-of-sample P&L is greater than zero and the out-of-sample profit factor is greater than 1, using the same profit-factor rule.

These thresholds were set before the candidate results were calculated. They are a screen, not a claim that 0.25 or 100 trades is an optimal risk limit. If more than one candidate passes, order them by out-of-sample spread-only profit factor and then by lower out-of-sample drawdown. Do not combine pieces of different strategies.

The R.30 holdout is not independent evidence for a name selected in this screen. A pass would still require a later study on data that this screen did not use to choose the name.

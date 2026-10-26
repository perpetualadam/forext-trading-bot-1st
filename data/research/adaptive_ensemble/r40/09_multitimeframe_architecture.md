# R.40 multi-timeframe architecture

This is a research layout. It is not connected to `bot_loop`, order execution, position sizing, or the six strategy flags.

## Roles

- H4 supplies context: the confirmed trend, range, or `UNCERTAIN` state.
- H1 supplies structure: confirmed swings and lines on the hourly clock.
- M5 may later supply a timing bar. R.40 does not define an entry order.

## Clock

Each series carries `time` as the UTC open and `available_at` as the close time. An M5 bar that opens at `t` is known at `t + 5 minutes`. An H1 candle is known one hour after its open. An H4 candle is known four hours after its open.

An as-of join at decision time `t` may attach the latest H1 and H4 rows whose `available_at` is less than or equal to `t`. The H4 candle that contains `t` is unfinished. Its eventual close stays invisible to every M5 row inside that same four-hour block. The same rule applies to the current H1 hour. `visible_close` implements this read and is covered by an offline test.

## Missing data

If the required completed H4 or H1 candle is absent, the feature is `UNCERTAIN` and the research decision is `NO_TRADE`. A weekend, a holiday gap, or a bucket with a missing M5 bar all take this path. The last price is not carried forward.

## Provenance and pip size

Every feature row should retain the source file hash, the aggregation rule, the structure definition id `r40.structure.v1`, the confirmation width `k`, and the decision timestamp. Pip size follows the quote currency: 0.01 when the quote is JPY, otherwise 0.0001. USD_JPY is the only current file on the 0.01 rule.

## Separation

Analysis code lives under `forex_bot/research/learning/`. It does not submit an order, change a strategy flag, or vote in the ensemble. A research output of `BUY` or `SELL` would still be a hypothesis until a later stage with fresh data says otherwise. `NO_TRADE` and `UNCERTAIN` are explicit states, not blank values to be filled by a default direction.

# R.40 cost and holding-period considerations

Higher-timeframe research changes the intended holding clock. It does not create an edge. R.38 found that recent M5 movement size is somewhat associated with later absolute movement, and that the same features did not pay for a directional trade after the spread. R.39's one-hour maximum hold lost money after bid/ask costs. A four-hour or multi-day hold still pays the entry spread and can add overnight, weekend, financing, and gap exposure.

## What the local candles can support

The median M5 close spread on the stored year is about 1.3 pips for AUD_USD, 1.6 for EUR_USD, 1.9 for GBP_USD, 1.8 for USD_CAD, 1.5 for USD_CHF, and 1.6 pips for USD_JPY at a pip of 0.01. Those are descriptive medians of `ask_close - bid_close` in the files. They are not a live quote and not an account spread schedule.

A completed H1 candle spans 12 M5 bars. A completed H4 candle spans 48. With `k = 2`, an H1 swing is known when the second later hour completes, three hours after the pivot hour opens. An H4 swing is known when the second later four-hour candle completes, twelve hours after the pivot candle opens. A study that then holds for one or more higher-timeframe candles is an overnight study whenever the hold crosses the account's financing time, and a weekend study whenever it is open through the Friday-to-Sunday gap.

The files show 51 gaps longer than 48 hours on every pair, with a largest gap of 49.08 hours. A position held into that gap is exposed to the reopen. The files record the gap. They do not record the financing charge, the slippage at the reopen, or the margin call rule.

## What must be verified before any operational use

The user's test-account balance is not a transaction-cost input. The historical bid/ask spread is not the GBP spread-betting contract. Before any later stage treats these ideas as executable, the account-specific items below need their own authorised check:

- Whether the GBP spread-betting account lists the instrument.
- The spread-bet price, stake size, and minimum stake.
- The bid/ask or spread convention that account actually applies.
- Overnight financing, the time it is charged, and the weekend convention.
- Margin requirement and margin close-out rule.
- Any guaranteed-stop or slippage-protection charge.
- Whether profit and loss are already in GBP, or whether a USD, JPY, CAD, CHF, or AUD quote must be converted, and at what rate.
- Whether practice and live contracts differ.
- Correlation limits across EUR, GBP, AUD, and JPY positions that can lose together.

None of those figures was requested from OANDA in this stage, and none was estimated.

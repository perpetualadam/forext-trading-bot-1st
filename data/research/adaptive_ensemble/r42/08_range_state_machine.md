# R.42 range state machine

States: `UNCERTAIN`, `CANDIDATE`, `CONFIRMED`, `INVALIDATED`.

- No eligible uncrossed pair: `UNCERTAIN`.
- Latest eligible support and resistance, with support strictly below resistance: `CANDIDATE`.
- Two completed support reaction episodes and two completed resistance reaction episodes after the pair exists: `CONFIRMED`.
- A completed close strictly outside either boundary, before or after confirmation: `INVALIDATED`. The reason is `close_outside`.
- A newer eligible pair replaces the previous pair. The reason is `latest_levels_changed`. Replacement is recorded separately from price invalidation. The old range is not rewritten and is not repaired with a different historical boundary. Evaluation of the replaced range stops.

A candidate is not reported as a confirmed range. A confirmed range does not stay active after a qualifying outside close.

If confirmation and replacement occur on the same candle, the range record can be `CONFIRMED` while the candle-end state is the new candidate. The confirmation time remains the availability time of that candle.

Missing candles, gap-rejected swing windows, and unfinished higher-timeframe buckets leave the missing information unavailable. They do not forward-fill a state.

At the sample end, an open candidate stays a candidate. No partial candle confirms or invalidates it.

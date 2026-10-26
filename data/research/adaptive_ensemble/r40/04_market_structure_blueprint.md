# R.40 market-structure definition blueprint

Identifier: `r40.structure.v1`. Status: design only. These definitions were not applied to the September 2025–August 2026 prices, and no trading signal was emitted.

The proposed confirmation width is `k = 2` completed candles of the timeframe under study. That value is a pre-registered design choice for a later stage. R.40 did not compare other widths.

## Shared availability rules

- Required history is the completed candles inside the definition's window.
- A fact that needs later candles becomes available at the `available_at` time of the last required candle. For an aggregated candle that time is its UTC open plus its period.
- An unfinished H1 or H4 bucket, or a source bar flagged incomplete, is not an observation.
- A missing constituent leaves the higher-timeframe candle absent. The definition returns `UNCERTAIN` for any structure that required that candle. Prices are not interpolated.
- A confirmed structure point keeps its confirmation time. Later candles may add a new point. They do not rewrite the earlier point.
- A live-equivalent pass may read only candles whose `available_at` is at or before the decision time.

## Swing high and swing low

A completed candle `i` is a swing high after candles `i+1` and `i+2` have completed, and only if its high is strictly greater than the highs of `i-2`, `i-1`, `i+1`, and `i+2`. A swing low uses lows and strict inequality. Ties are not swings under this definition. The pivot is located at candle `i`, and the earliest time it may be used is the completion time of candle `i+2`. Using it on candle `i` would treat the future confirmation candles as already known.

## Higher highs, higher lows, lower highs, lower lows

Compare a swing only with the previous swing of the same kind that is already confirmed. A higher high is a confirmed swing high above the prior confirmed swing high. A higher low, lower high, and lower low follow the same timing. The comparison becomes available when the newer swing is confirmed, not when its pivot candle opens.

## Trend state

`UNCERTAIN` until two confirmed swing highs and two confirmed swing lows exist. `UPTREND` when the latest confirmed high is a higher high and the latest confirmed low is a higher low. `DOWNTREND` is the mirror. A mixed pair of swings is `TRANSITION`. In any later research protocol, `UNCERTAIN` and `TRANSITION` map to `NO_TRADE`. The state can change only at a swing confirmation time.

## Trendline

A support line requires two confirmed swing lows. A resistance line requires two confirmed swing highs. The line exists at the confirmation time of the later pivot. Its slope uses the pivot candles' timestamps and prices. Geometry may pass through those two pivots. The line is not available before the second confirmation. A newer swing creates a new line with a new availability time and leaves the old line unchanged for decisions that already used it.

A touch is a later completed candle whose low, for support, reaches the projected line and whose close finishes back on the supported side. A break is a later completed candle whose close finishes beyond the line. Both are known at that candle's completion time. Wick penetration alone is not a break. Any distance buffer must be frozen before outcomes are examined. R.40 does not select one.

## Support, resistance, and range

A support candidate is the price of a confirmed swing low. A resistance candidate is the price of a confirmed swing high. A reaction is a later completed candle that touches the level and closes back inside. A range requires one support and one resistance, at least two reactions at each, and no completed close beyond either level between the first and last of those reactions. The range becomes known at the completion time of the candle that supplies the last required reaction. Its width is recorded in price and in that candle's bid/ask spread. Width is a description, not an entry rule.

## Breakout, failed breakout, continuation, invalidation

A breakout confirmation is a completed close beyond a range boundary after the range is already known. A failed breakout is a later completed close back inside the range. The number of candles allowed for that return must be frozen before evaluation. R.40 does not choose it from results.

Trend continuation is an existing `UPTREND` or `DOWNTREND` that remains intact after a new confirmed swing. A pullback inside an uptrend is a confirmed swing low that is still a higher low. It is known at that swing's confirmation time, two candles after the pivot.

The trend state leaves `UPTREND` or `DOWNTREND` at the confirmation time of the swing that breaks either sequence. An uptrend ends when a confirmed swing high prints below the prior confirmed swing high, or a confirmed swing low prints below the prior confirmed swing low. A downtrend ends on the mirror breaks. The resulting state is `TRANSITION`.

## What this blueprint refuses to do

Historical charts sometimes draw a line through pivots that were only identifiable later, then read that line at earlier bars. That construction is lookahead. R.39's five-bar and twenty-bar moving-average comparison, and its twenty-bar breakout window, remain short M5 calculations. They are not this swing definition, and their negative results stay negative.

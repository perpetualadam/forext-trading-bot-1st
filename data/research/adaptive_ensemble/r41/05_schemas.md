# R.41 schemas and conventions

Parent definition `r40.structure.v1`. Implementation `r41.structure.v1`. Protocol SHA-256 `8880d210ca38e783c1a2615c50a90688ed75825adf1652e525a5bfe55b60e1d0`, recorded before the descriptive run. Code SHA-256 `b9dd4a4fb133a42bd1cf2ec0615bca64f1299e5568e7d392e21f82c8d12943bc`.

## Swing

Fields: instrument, timeframe, swing type, pivot time, pivot price, confirmation time, availability time, source hash, definition version, relation, relation reason, compared-with id. Price is the bid high or bid low. Confirmation time and availability time are the same instant: the close of the second later candle. With `k = 2` that is three periods after the pivot open. Ties are counted and are not swings. A window that skips a period is rejected.

## Trend state

`UPTREND` is a confirmed higher high together with a confirmed higher low. `DOWNTREND` is a confirmed lower high together with a confirmed lower low. A mixed pair is `TRANSITION`. A missing or equal-price relation is `UNCERTAIN`. The state is stored on each completed candle and changes only when a newly available swing changes one of those relations. None of these states is a buy or a sell.

## Trendline

A line joins a swing to the immediately previous swing of the same type. Lows make a support line. Highs make a resistance line. The line's availability time is the later swing's confirmation time. Slope is the price change divided by elapsed UTC seconds, so a weekend stays in the denominator. A newer swing adds a new version and leaves the old version's availability time unchanged.

## Touch and break

The line is sampled at the candle's close time. Events start strictly after the line exists.

- `TOUCH_REACH`: the wick reaches or crosses the line and the close finishes back on the original side. No pip band is added.
- `TOUCH_EXACT`: the subset of reaches whose wick equals the line within `1e-8` price units. That tolerance is numerical equality.
- `BREAK`: the first close strictly beyond the line.
- `BEYOND_CONTINUATION`: later candles that stay beyond the same line. This count grows with every retained historical line. It is not a count of separate breaks.
- `CLOSE_ON_LINE`: the close equals the line numerically. It is not a break.

A wick through the line with the close back on the original side is a touch.

## Support, resistance, and range

Each confirmed swing low is a support level and each confirmed swing high is a resistance level from that swing's confirmation time. Later reaches and first closes beyond the price are counted. The level is not removed. R.40 did not define level retirement.

A range stays `UNCERTAIN`. The reaction idea is defined for one level. The choice of which support pairs with which resistance is not. No range object is emitted, and a later break is not used to choose earlier boundaries.

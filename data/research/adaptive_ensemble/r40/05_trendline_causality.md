# R.40 trendline causality

A trendline in this design is a function of confirmed swings, and a swing is a function of already completed candles.

For an H1 chart, a pivot at 10:00 UTC with `k = 2` needs the 11:00 and 12:00 candles. The 12:00 candle completes at 13:00 UTC. The pivot may enter a line only at 13:00 UTC. A second pivot at 16:00 UTC needs the 17:00 and 18:00 candles and becomes usable at 19:00 UTC. The line that joins them is usable at 19:00 UTC. Any touch or break is a third, later completed candle.

The same clock applies on H4. Two confirmation candles add eight hours. An H4 pivot is not known on the M5 bars inside its own four-hour bucket, and it is not known during the two following H4 buckets.

Prefix stability follows from the same rule. Deleting candles after a line's availability time leaves that line unchanged. Deleting one of the confirmation candles removes the swing. The aggregation tests already check the candle form of this rule: the first complete H1 close is unchanged when later M5 bars are removed, and an as-of read during the hour does not see that hour's close.

Gaps break the window. If any of the five candles in a `k = 2` swing window is absent, the result is `UNCERTAIN`. A weekend sits inside that class. The line is not extended across the missing candles, and the missing hours are not filled with the last traded price.

Repainting would mean recomputing an old line after a newer pivot appears and then storing the new value at the old time. The research record needs both objects: the original line with its original availability time, and the new line with the later availability time.

No line was fitted to the local year in this stage.

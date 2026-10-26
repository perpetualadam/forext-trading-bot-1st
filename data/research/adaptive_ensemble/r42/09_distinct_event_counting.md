# R.42 distinct-event counting

These counts are descriptive. They are not trade opportunities and they are not independent samples. The six USD instruments share one research-exposed year.

Counted separately:

- Confirmed swings, from the unchanged R.41 detector.
- Newly created support and resistance levels.
- Level invalidations.
- Level supersessions.
- Newly created trendlines.
- First trendline breaks.
- Trendline supersessions.
- Distinct line-touch episodes.
- Support-touch episodes.
- Resistance-touch episodes.
- Range-pair creation.
- Confirmed range creation.
- Range invalidation.
- Candles whose recorded state is `UNCERTAIN`.

An episode is the first candle of an uninterrupted interaction. Adjacent candles in that interaction are not extra events.

Support and resistance touch episodes can overlap range-reaction episodes while a pair is active. Those counts are not added together.

Range replacement is reported separately from range invalidation.

`legacy_raw_continuation_comparisons` is zero. This stage does not repeat the R.41 scan of every retained line against every later candle, and those raw comparisons are excluded from the distinct-event totals.

Distinct identifiers do not imply statistical independence.

# R.41 clock and prefix checks

The prefix cut is 2026-03-01 00:00 UTC. It is a causality check, not a market threshold. For every instrument and both H1 and H4, the swings, lines, states, trendline-event counts, and level-event counts available by that time match a run that never saw the later candles. The descriptive script exits if any of those comparisons differ.

On each of the six pairs the clock checks passed:

- An H1 swing is absent one second before its confirmation time and present at that time.
- An H4 swing follows the same rule.
- An M5-style timestamp 30 minutes after an H1 open does not see that hour.
- An M5-style timestamp five minutes after an H4 open does not see that four-hour candle.
- The H4 candle is absent one second before its close and present at the boundary.
- No swing is dated after the last completed candle.

These checks are stored in `13_descriptive_statistics.json` under `clock` and `prefix_invariant`.

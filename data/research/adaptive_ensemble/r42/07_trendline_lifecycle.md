# R.42 trendline lifecycle

Line geometry is unchanged from `r41.structure.v1`: two consecutive confirmed swings of the same kind, slope over elapsed UTC seconds, available when the second swing is confirmed.

States: `ACTIVE`, `BROKEN`, `SUPERSEDED`, `UNCERTAIN`.

A line is not active before its second source swing is confirmed.

A newer same-kind line supersedes the current `ACTIVE` line. The reason is `newer_confirmed_line`. A `BROKEN` line stays `BROKEN` and is not superseded.

The first later completed close beyond the active line is the only break. The reason is `close_beyond`. Later candles beyond that line are not additional breaks. The line is not reactivated if price later crosses back. After the break, that line is no longer compared with new candles.

Archived lines stay in the record for audit. They are not re-evaluated against every later candle. The R.41 raw continuation comparisons are not recomputed. Their count in this stage is zero and they are excluded from distinct-event totals.

An earlier active interval is not rewritten when a later line is created or when a later close breaks the successor.

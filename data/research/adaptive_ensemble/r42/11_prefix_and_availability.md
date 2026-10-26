# R.42 prefix invariance and multi-timeframe availability

Prefix cutoff: `2026-03-01T00:00:00Z`. This is a causality check. It is not a market threshold.

For each of the six instruments and both H1 and H4, the events produced from candles available at or before the cutoff matched the full-sample events whose availability time is at or before the cutoff. The comparison uses event type, related identifier, and availability time. Final status after the cutoff is allowed to change. Events known by the cutoff are not.

Clock checks passed on all twelve series:

- A level is absent one second before its availability time and present at that time.
- A higher-timeframe candle is absent at the midpoint of its own open interval and present at its close.
- Each side ends with at most one `ACTIVE` level and at most one `ACTIVE` line.
- Every confirmed range has two support reactions and two resistance reactions.

H1 and H4 are aggregated separately from the existing M5 files. An H1 or H4 state is visible at an earlier timestamp only when its `available_at` is at or before that timestamp. An unfinished H1 or H4 bucket stays rejected. H4 information is not attached to earlier H1 or M5 rows. No production multi-timeframe vote is implemented.

The descriptive run exited 0. A prefix or clock mismatch would have stopped the script before writing counts.

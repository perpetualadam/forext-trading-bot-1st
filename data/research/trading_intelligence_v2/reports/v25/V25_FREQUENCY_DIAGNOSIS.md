# V2.5 Frequency Diagnosis

M5 observed-only baseline counts:
{
  "candidate_signals": 9267,
  "accepted_entries": 807,
  "repeated_direction": 8426,
  "adjacent_signal": 6719,
  "existing_position": 3584,
  "immediate_reentry": 811,
  "reentry_after_stop": 317
}

Frequency means candidate signals as well as actual entries; signals while a
position exists are not multiple executed trades. Records flag repeated direction,
adjacent M5 signals, existing-position rejection, <=one-M5-bar reentry after an
exit and stop reentry. That one-bar interval is descriptive, never a cooldown.
Counts are available by instrument, strategy, timeframe, session, regime,
volatility, weekday and current spread/ATR condition; durations and USD turnover
use executed trades. Six M5 standalone-strategy baseline portfolios provide
frequency diagnostics, not six independent diversification streams.

V23's near-99.42% scalp/trend active agreement remains prior descriptive evidence;
different predicates are not deduplicated merely because directions agree.
unique_votes consolidates only identical predicate identity, instrument, time
and side. E supplies one pinned-strategy predicate per candidate, so E is exactly
baseline-equivalent; no independent opportunity is suppressed. Correlated signals
are not counted as independent statistical observations. Neither repeated counts
nor cost savings alone establish excessive economic trading frequency.

Research only. Production remains NO-GO.

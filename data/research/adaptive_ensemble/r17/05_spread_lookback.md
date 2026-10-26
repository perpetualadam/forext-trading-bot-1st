# Spread and lookback

No approved numeric entry-spread threshold exists in the trading configuration. None was invented. Evidence `spread_limit` is `not_approved`. A finite spread, including 0.05, is not recorded as a passed spread check and is not blocked by a number this stage made up.

Structural checks do block, before reservation and adapter dispatch:

- Missing, non-finite, or non-positive bid or ask.
- Ask below bid.
- A non-numeric spread string.
- Candle count below the lookback requirement.
- A candle that is not an object, has no close, or has a non-numeric OHLC field.
- A non-finite OHLC value.
- A timestamp that cannot be parsed.
- A timestamp strictly earlier than the previous one.

Spread units are price units: ask minus bid. No pip table was added.

Lookback uses the selector value when it is a positive integer. Otherwise a name containing `swing` uses `SWING_LOOKBACK` (default 100), a name containing `scalp` uses `SCALP_LOOKBACK` (default 50), and every other name uses `DEFAULT_INDICATOR_LOOKBACK` (50). The selected value is not lowered.

Duplicate timestamps are recorded and do not by themselves block. The isolated fixtures share that treatment.

Quote age uses the existing `MANAGE_PRICE_STALE_SEC` of 90 only when both `quote_as_of` and `now` are set. A future timestamp blocks. A missing timestamp stays `quote_freshness: not_evaluated`.

Synthetic bid and ask are accepted only inside the isolated harness. Production market provenance remains NOT_EVALUATED.

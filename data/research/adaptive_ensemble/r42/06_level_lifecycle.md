# R.42 support and resistance lifecycle

States: `ACTIVE`, `INVALIDATED`, `SUPERSEDED`, `UNCERTAIN`.

A level is created `ACTIVE` at the confirmed swing's availability time. The reason is `confirmed_swing`. The confirmation candle does not invalidate the level it creates.

A later completed close strictly through the price sets `INVALIDATED`. The reason is `close_through`. The effective time is that candle's availability time. A wick that closes back on the original side is a touch episode, not an invalidation.

A newer confirmed level of the same kind sets the previous `ACTIVE` level to `SUPERSEDED`. The reason is `newer_confirmed_level`. An already invalidated level stays `INVALIDATED`.

On a candle that both closes through an old level and confirms its replacement, invalidation is applied first. Supersession occurs only if the old level is still `ACTIVE`.

Old levels remain in the record. They are not deleted when they stop being eligible for a new pair.

No distance, volatility, or age threshold is applied.

At the end of the dataset, each side has at most one `ACTIVE` level. Zero active levels is allowed when the last relevant level was invalidated and no later swing of that kind was confirmed.

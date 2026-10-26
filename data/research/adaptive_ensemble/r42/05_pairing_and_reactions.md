# R.42 support/resistance pairing and reaction episodes

Definition version: `r42.structure.v1`. Parent: `r41.structure.v1`. Ancestor: `r40.structure.v1`.

Protocol SHA-256: `da8f53c0f8b89037ab00721f4c0a3b8d7c322d6da692e37a2b3f142a643c6b27`.

Lifecycle module SHA-256: `4ed6fb9d53b2c67930e1367303c50a48a06f51b266c4b99a6655dda32162cba5`.

The protocol file was hashed before the descriptive run. The descriptive script refuses to run if either hash changes.

## Pairing

- Support candidates are confirmed swing lows. Resistance candidates are confirmed swing highs.
- The pair uses the latest `ACTIVE` support and the latest `ACTIVE` resistance.
- Both levels must already be available. The pair becomes available at the later of the two availability timestamps.
- Support price must be strictly below resistance price.
- A missing side, a superseded level, an invalidated level, or a crossed pair produces no candidate. The candle state is `UNCERTAIN`.
- A crossed identity is counted once. The same two level identifiers are not counted again on later candles.
- Swings that share an availability timestamp are applied in pivot-time order, then swing type. `HIGH` is applied before `LOW`.
- Older level combinations are not searched. Later reversals do not choose the boundaries.
- `Stale` means the level is no longer `ACTIVE`. There is no age, distance, or volatility expiry.

## Reaction episode

A reaction reuses the R.41 reach rule. The absolute tolerance `1e-8` is numerical equality. It is not a pip band and it was not searched.

A support reaction starts when a later completed candle's low reaches the support and the close finishes at or above it. A resistance reaction is the mirror. The original pivot and the confirmation candle are excluded because the level is not yet available strictly before those candles.

Adjacent candles that keep reaching the same boundary are one episode. A candle that does not reach ends the episode. The next reach can start another episode.

Range reactions count only episodes that start after the pair exists. An episode already open before the pair does not count toward that pair.

Two support episodes and two resistance episodes confirm a candidate. The confirmation timestamp is the availability time of the candle that completes the second episode on the lagging side.

A completed close strictly outside either boundary invalidates the candidate or the confirmed range. That candle is not also counted as a reaction.

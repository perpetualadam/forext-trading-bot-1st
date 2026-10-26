# R.42 limitations

- The reaction rule is exact reach with numerical tolerance `1e-8`. It was frozen before the counts. It was not loosened after the year produced one confirmed range.
- That single GBP_USD H1 confirmation and its replacement share the candle at 2026-05-20 09:00 UTC. No completed candle ended with an active confirmed range.
- H4 produced no confirmed range under the same rule.
- Almost every candidate ended by an outside close or by a newer level before two reactions had accumulated on both sides.
- Latest-level pairing produced no crossed pair on these twelve series. The crossed path remains fail-closed and was tested on synthetic prices.
- Replaced ranges are not rechecked against later closes. A later close through an archived boundary is not an extra invalidation.
- Active-only evaluation does not emit touch or break events for archived lines and levels.
- Level-touch episodes and range-reaction episodes overlap during an active pair. They are separate descriptions of related candles.
- Candle counts in `UNCERTAIN` are completed candles. They do not fill weekend or missing-data gaps.
- The six instruments are correlated USD pairs over one research-exposed year. Sums across instruments are not six independent samples.
- No bid/ask execution, financing, or spread is applied. Range width in pips is price geometry.
- No model was trained. No parameter was searched. No trading signal was emitted.

# Gate F — market-data and quote contract mapping

MARKET CONTRACT MAPPED. No market data was downloaded. Production quote and candle provenance remain MISSING_EVIDENCE.

| Item | Interface | Classification |
|---|---|---|
| Instrument name | `normalize_oanda_symbol` / `oanda_instrument` | SOURCE_INTERFACE_IDENTIFIED |
| Bid and ask | `IterationDependencies` on the shared path; `fetch_pricing_snapshot` for a broker quote | harness fields are not production provenance |
| Midpoint | not an entry-gate input | MISSING |
| Quote timestamp | `quote_as_of`; missing blocks `quote_timestamp_missing` | harness only |
| Acquisition timestamp | no separate `quote_acquired_at` | MISSING |
| Quote provenance | `production_quote_provenance` standing gap | MISSING_EVIDENCE |
| Spread units | price, `ask - bid` | recorded; POLICY_UNAPPROVED as a limit |
| Pip units | `profit_protection.pip_size`: 0.01 for JPY, else 0.0001 | SOURCE_INTERFACE_IDENTIFIED; not an entry cap |
| Candle time | `_candle_time_to_naive_utc` | not called |
| Candle completeness | `_market_entry_block` rejects malformed, non-finite, and short history | runtime on injected candles |
| Candle source | `fetch_ohlcv` / `fetch_ohlcv_range` | NOT_EVALUATED |
| Lookback | selector value, else scalp/swing/default 50 | runtime |
| Cache | `state.pricing_snapshot` | LOCAL_FALLBACK_ONLY |
| Freshness | existing `MANAGE_PRICE_STALE_SEC` = 90 when both times exist | harness window only |
| Conversion | not in the quote gate | MISSING |

Quote-basis inconsistency, left unchanged:

- Spread structure uses bid and ask.
- Position sizing and portfolio stop-risk use `dependencies.price`.
- The shared FakeBroker request sets `entry_quote` to None.
- The sealed binding stores bid and ask when both exist.
- The production adapter is not invoked by that path, so the inconsistency cannot authorise a broker order.

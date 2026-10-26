# Market snapshot contract

`_unified_market_snapshot` builds one quote after the structural market checks pass.

- BUY sizing and the entry quote use the ask.
- SELL sizing and the entry quote use the bid. The observed two-cycle trace is a BUY. The SELL side is the other branch of the same function.
- Spread is `ask - bid` in price units. The numeric spread policy stays `POLICY_UNAPPROVED`.
- Stop distance is applied to that executable price. The sizing formula itself is unchanged.
- Quote timestamp is `quote_as_of`. Acquisition timestamp is the injected clock. Candle timestamp stays on the candle. Those fields are separate. In the observed cycle they were 12:00:00 and 11:58:00.
- A missing bid or ask, a stale quote, or a missing quote timestamp still blocks before sizing.
- An explicit non-finite or non-positive injected price still blocks. A finite injected mid that differs from the executable side is recorded as `injected_price_not_used` and is not used.
- The candle close is no longer a silent sizing fallback on this path.
- Provenance on this path is `synthetic_harness`. Production market provenance stays `MISSING_EVIDENCE`.
- The legacy `run_bot` pricing path was not executed and its sizing formula was not edited.

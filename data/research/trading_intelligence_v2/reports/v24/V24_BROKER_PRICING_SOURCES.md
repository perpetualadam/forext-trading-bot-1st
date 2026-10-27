# V2.4 Broker Pricing Sources

Public documentation accessed 2026-10-27; no authenticated services.

- OANDA Europe Limited / UK, forex/CFDs, retail plan not established:
  https://www.oanda.com/uk-en/trading/our-pricing/ describes liquidity-provider
  prices. Starting spreads are not historical averages or this archive's tier.
- UK v20/v20 MT4 cash settlement, home currency:
  https://www.oanda.com/uk-en/trading/our-charges/ states midpoint conversion with
  1% markup/markdown, restricted there to v20 and v20 MT4. Account applicability
  is unknown. No unverified GBP commission tariff was inferred.
- UK funding, instrument currency converted to account currency:
  https://www.oanda.com/uk-en/trading/financing-costs/ gives instrument/direction
  dependent rates and New York rollover; its worked conversion uses 0.5%, in
  conflict with the charges page. Historical applicable rates not acquired.
- UK OEL execution policy (May 2025):
  https://legal.oanda.com/?code=execution_policy_oel&language=en describes
  market-dependent slippage in either direction and volatility risks.
- US core pricing, comparator ONLY:
  https://help.oanda.com/us/en/faqs/spreads-commission.htm documents USD0.70 per
  10,000 units per leg, prorated. It is not a UK commission entitlement.
- BVI core pricing, not used in replay:
  https://help.oanda.com/bvi/en/faqs/spreads-commission.htm instead documents
  USD40/million USD notional per leg charged both upfront. Jurisdictions and
  billing bases must not be interchanged.

Public documents partly verify pricing mechanisms; actual account pricing is
BROKER_PRICING_NOT_VERIFIED. Minimum commission, guaranteed stops, platform
differences and tier eligibility remain unestablished. No claim of historical
or current user-specific tariff. No guessed financing rates were introduced.

Production remains NO-GO. Research simulation only; the 29-day archive was previously examined.

# V2.4 Currency Conversion

P/L in quote currency is sign*(exit_fill-entry_fill)*base_units. USD
accounts use identity conversion for EUR/GBP/AUD_USD quote P/L. USD_JPY/CAD/CHF
require quote-to-USD conversion; GBP accounts also require a causal GBP_USD leg.
Positive base-to-quote assets use bid, negative liabilities ask; inverse assets
divide by ask, inverse liabilities by bid. Graph edges must be <=300 seconds old
and not future. No available path rejects; no 1:1 fallback. The 300-second budget
is this M5 simulation assumption, not a broker snapshot guarantee.

Decimal independently reproduces the signed graph and all six pairs, both sides,
USD and GBP. Own-instrument conversion uses the existing execution-price override;
this is synthetic, not an independent broker conversion quote. V24 waterfall
separates spread and slippage as differences of converted P/L, avoiding false
linearity across a P/L sign change. Legacy conversion_cost_residual is an
attribution discrepancy, not a measured broker fee.

Published UK charges describe midpoint conversion with a markup for specified
subaccounts. The research signed-bid/ask conversion is not that settlement model.
Public UK financing examples use a different percentage from the charges page;
this documentary discrepancy remains unresolved. No actual account data was read.

Production remains NO-GO. Research simulation only; the 29-day archive was previously examined.

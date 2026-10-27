# V2.4 Final Decision

TIV24_COST_MODEL_PARTIALLY_VERIFIED.

Independent findings: COST_MODEL_PARTIALLY_VERIFIED; no demonstrated cash
accounting defect corrected; BROKER_PRICING_NOT_VERIFIED for the actual account.
No spread double-charge found. Declared slippage/commission are correct on both
sides. All six pair pip sizes and USD/GBP conversion/sizing are internally tested.
The reproduced M5 loss is largely spread, then hypothetical commission and
slippage. Model and pricing assumptions prevent a broker-realism certification.

Recommended next improvement: establish an explicit reviewed pricing scenario
for jurisdiction/platform/plan without credentials, and obtain approved historical
settlement/funding evidence before separately implementing a broker-specific
conversion/funding model. Preserve this baseline and make any future model a
separate version. Do not optimise the strategy to compensate for unverified fees.
Stop after V2.4. No operational integration or trading enablement.

Production remains NO-GO. Research simulation only; the 29-day archive was previously examined.

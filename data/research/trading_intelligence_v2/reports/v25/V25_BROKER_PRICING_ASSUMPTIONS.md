# V2.5 Broker Pricing Assumptions

The V24 source review was inspected; public UK charges were rechecked
2026-10-27: https://www.oanda.com/uk-en/trading/our-charges/ . Public documents
cannot identify the user's jurisdiction, account type, pricing plan, account
currency or entitlement. No credentials or authenticated broker data were read.
No US commission rate is treated as a UK plan.

OBSERVED_BID_ASK_ONLY: existing observed bid/ask, zero extra commission/slippage.
This is an archive diagnostic, not a broker-pricing applicability certification.
HYPOTHETICAL_STRESS: same observed spreads plus 0.5 pip adverse per actual fill
and 3 account units per 100k base units per side. This rate is unverified.
HYPOTHETICAL_BASELINE: original 0.2 pip/side plus commission3, unchanged control.
DOCUMENTED_SPREAD_ONLY and DOCUMENTED_COMMISSION_PLAN are supported by the
evaluator only with explicit applicability; both are disabled in this study.
Pricing is never chosen using performance. All portfolio runs are USD; GBP
pre-entry conversion is synthetic-tested, not presented as verified GBP pricing.

V24's signed bid/ask FX conversion and UTC-date financing remain hypothetical.
The cost estimate assumes intraday flattening and no estimated funding; it does
not promise broker rollover avoidance or calculate undocumented financing.
Current-spread persistence is an estimate, not a known future exit spread.

Research only. Production remains NO-GO.

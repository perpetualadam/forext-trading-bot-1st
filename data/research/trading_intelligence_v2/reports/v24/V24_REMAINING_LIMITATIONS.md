# V2.4 Remaining Limitations

No independently unseen data; short archive, overlapping strategies/scenarios.
No actual user plan, jurisdiction attestation, commission minima or tier pricing.
No contemporaneous intrabar bid/ask path, order-book depth or empirical latency.
OHLC both-hit uses pessimistic stop-first; exit time upper bound is not tick time.
Opening spread proxy may misattribute intrabar costs. The synthetic execution FX
override is not independently observed broker settlement. Signed executable FX
differs from published UK midpoint markup. Financing UTC-date flat rate is not
NY rollover, holiday/weekend schedule, directional historical rate or broker fee.
GBP sizing consistency does not establish broker-realistic GBP results. No
documented commission scenario is claimed applicable to this user's account.
The US comparator retains the archive's unknown spread tier and is hypothetical
as a combined product. All adverse slippage and stress factors are assumptions.
No operational model correction, integration or live readiness is authorised.
The local bot_loop raw seal mismatch remains a separate pre-existing issue.

Production remains NO-GO. Research simulation only; the 29-day archive was previously examined.

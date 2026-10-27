# V2.5 Cost Opportunity

For units U, current spread a-b, pip p, per-side assumed slippage s pips:
spread quote debit=U*(a-b), slip quote debit=2*U*s*p. Convert each liability with
V24's independent Decimal converter and add two explicit account-currency fees.
Do not debit these estimates from replay cash: actual bid/ask fills already
contain spread. Execution P/L still reconciles through the V24 cost ledger.

spread_pips=(a-b)/p; spread_ATR=(a-b)/ATR; spread_stop=(a-b)/stop_distance;
spread_target=(a-b)/target_distance. cost_R=estimated_account_cost divided by
spot liability value of stop_distance*U; cost_target uses target_distance*U.
This price-only R denominator is labelled separately from engine initial risk,
which includes planned exit slippage, commissions and stop-price FX.

Illustrative binary MID-REFERENCE payoff: win +T, lose -S, fixed cost C each trade.
Break-even win rate=(S+C)/(S+T); >1 means unattainable under that assumed payoff.
It is not a forecast probability and not the engine's fill-anchored target payoff.
Target is intended geometry, not expected movement; expected_gross_movement=None.
Current-spread and spot FX estimates may differ from exit costs. Future realised
MFE, MAE, returns, spread or FX cannot affect a decision.

Research only. Production remains NO-GO.

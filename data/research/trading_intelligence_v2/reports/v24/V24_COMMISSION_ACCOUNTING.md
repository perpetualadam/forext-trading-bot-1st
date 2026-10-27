# V2.4 Commission Accounting

Config's 3 account-currency units per 100,000 base units PER SIDE is an
explicit research assumption. 10,000 units cost 0.3 on entry and 0.3 on exit,
0.6 round trip, regardless of BUY/SELL. It is not USD notional and not an OANDA
plan identification. There is no minimum commission in this model. With GBP
account it means GBP 3 per 100k side, not USD 3 silently relabelled GBP.

fee_account tests separately specified foreign-currency fees using liability
conversion; the replay's baseline commission is already in account currency.
Sensitivity B/C use zero extra commission; D retains the hypothetical baseline.
F uses a documented US rate only as a labelled non-UK comparator on these same
observed spreads, NOT a reconstruction of a core-spread feed or applicable plan.
Actual account plan, minimum fee and archive price tier remain unknown.

Production remains NO-GO. Research simulation only; the 29-day archive was previously examined.

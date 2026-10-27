# V2.4 Position Sizing

Default account equity 10,000 and risk fraction 0.0025 give a 25 account-unit
budget. Stop distance max(2*ATR, 4*pip), target 2*stop, unchanged. Per-base-unit risk
= account liability conversion(stop_distance + exit_slip at assumed stop fill)
+ twice per-side account commission. Units=floor(min(25/risk_unit,
remaining_portfolio_risk/risk_unit, remaining_margin*leverage/notional_unit)).
Notional is liability-valued base currency in account currency. Margin=notional/20;
default allocation ceiling 80% equity, portfolio risk 2%, six positions and two
same-USD-direction slots. These are frozen research values, not account limits.

Example USD_JPY: 10,000 units * .01 = JPY 100 per pip. At bid150/ask150.02,
a JPY100 debit costs USD100/150, or GBP100/150/1.25 with GBP_USD bid1.25.
USD_CAD/CHF use .0001 times base units and their own conversion, never the JPY pip.
Tests cover all six pairs/sides/accounts and check budget and margin ceilings;
an exact EUR_USD stop oracle verifies the floor and realised loss under assumed
fill. GBP sizing is internally consistent with these hypothetical conversions,
not verified against broker markup, tier margin or account settings. Overnight
financing and gaps are not guaranteed by the intended stop-risk budget.

Production remains NO-GO. Research simulation only; the 29-day archive was previously examined.

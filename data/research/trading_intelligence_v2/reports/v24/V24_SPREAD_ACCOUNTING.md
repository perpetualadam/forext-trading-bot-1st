# V2.4 Spread Accounting

No second spread fee is subtracted. BUY ask entry/bid exit and SELL bid
entry/ask exit already contain spread. For flat midpoint m, units U and spreads
se,sx, quote P/L = -U*(se+sx)/2 without slippage or fees. For constant spread this
is one full spread, not two full spreads. Immediate same-candle exits still use
both executable sides; there is no synthetic spread debit.

Legacy spread_cost_account attributes U*(se+sx)/2 converted as a liability.
Because signed bid/ask conversion is nonlinear across zero, attribution need not
sum to gross-net without the small conversion residual. V24 instead uses a
sequential converted-P/L waterfall. Neither attribution is another cash charge.
Widened stress replaces the bid/ask half-width around each quoted midpoint;
it never adds another spread fee. Trigger-implied intrabar midpoint is unknown
in real ticks; the opening spread proxy cannot establish realised market spread.

Production remains NO-GO. Research simulation only; the 29-day archive was previously examined.

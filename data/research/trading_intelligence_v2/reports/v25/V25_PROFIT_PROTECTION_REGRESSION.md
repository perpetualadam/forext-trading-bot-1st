# V2.5 Profit Protection Regression

forex_bot/profit_protection.py is unchanged. The actual existing source
is reused through Existing:67% original TP-distance activation, ATR14*0.5,
four-pip fallback, monotonic ratchet, BUY/SELL and JPY pip precision. No parameters
were optimised. Fixed baseline protection-on comparisons were replayed under
both pricing cases across all four entry timeframes; no protection variant was
selected by its result. Earlier source-backed suites and V25 engine equivalence
checks are required and recorded in test_results.json. There are no broker
trailing stops, breakeven amendments or partial closes.

Research only. Production remains NO-GO.

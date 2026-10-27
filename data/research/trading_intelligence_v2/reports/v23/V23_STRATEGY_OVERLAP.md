# Redundancy and distinctness

Scalp and trend call the same existing signal_from_arrays dispatcher, but have separate branches. Trend permits close >= fast MA for BUY (<= for SELL); scalp requires strict > (<). They are not mathematically equivalent: at close==fast with fast>slow, trend buys and scalp waits. A deterministic counterexample executes the actual pinned functions. When both act, their directions cannot oppose under those conditions. No diversification benefit follows merely from different strategy names. Swing-trend shares the trend branch but uses a different lookback.

- AUD_USD/M5: common-ready=2436, BUY same=679, SELL same=715, opposed=0, joint WAIT=1028, scalp-only=0, trend-only=14, active conditional agreement=0.990057.
- AUD_USD/M15: common-ready=791, BUY same=214, SELL same=215, opposed=0, joint WAIT=359, scalp-only=0, trend-only=3, active conditional agreement=0.993056.
- AUD_USD/H1: common-ready=179, BUY same=38, SELL same=63, opposed=0, joint WAIT=77, scalp-only=0, trend-only=1, active conditional agreement=0.990196.
- AUD_USD/H4: common-ready=49, BUY same=8, SELL same=23, opposed=0, joint WAIT=18, scalp-only=0, trend-only=0, active conditional agreement=1.000000.
- EUR_USD/M5: common-ready=2448, BUY same=605, SELL same=810, opposed=0, joint WAIT=1029, scalp-only=0, trend-only=4, active conditional agreement=0.997181.
- EUR_USD/M15: common-ready=790, BUY same=186, SELL same=264, opposed=0, joint WAIT=338, scalp-only=0, trend-only=2, active conditional agreement=0.995575.
- EUR_USD/H1: common-ready=208, BUY same=40, SELL same=82, opposed=0, joint WAIT=86, scalp-only=0, trend-only=0, active conditional agreement=1.000000.
- EUR_USD/H4: common-ready=57, BUY same=0, SELL same=33, opposed=0, joint WAIT=24, scalp-only=0, trend-only=0, active conditional agreement=1.000000.
- GBP_USD/M5: common-ready=2438, BUY same=686, SELL same=720, opposed=0, joint WAIT=1020, scalp-only=0, trend-only=12, active conditional agreement=0.991537.
- GBP_USD/M15: common-ready=792, BUY same=229, SELL same=224, opposed=0, joint WAIT=339, scalp-only=0, trend-only=0, active conditional agreement=1.000000.
- GBP_USD/H1: common-ready=166, BUY same=56, SELL same=39, opposed=0, joint WAIT=71, scalp-only=0, trend-only=0, active conditional agreement=1.000000.
- GBP_USD/H4: common-ready=43, BUY same=6, SELL same=12, opposed=0, joint WAIT=25, scalp-only=0, trend-only=0, active conditional agreement=1.000000.
- USD_CAD/M5: common-ready=2455, BUY same=797, SELL same=636, opposed=0, joint WAIT=1006, scalp-only=0, trend-only=16, active conditional agreement=0.988958.
- USD_CAD/M15: common-ready=831, BUY same=309, SELL same=172, opposed=0, joint WAIT=348, scalp-only=0, trend-only=2, active conditional agreement=0.995859.
- USD_CAD/H1: common-ready=208, BUY same=94, SELL same=35, opposed=0, joint WAIT=79, scalp-only=0, trend-only=0, active conditional agreement=1.000000.
- USD_CAD/H4: common-ready=57, BUY same=32, SELL same=5, opposed=0, joint WAIT=20, scalp-only=0, trend-only=0, active conditional agreement=1.000000.
- USD_CHF/M5: common-ready=2404, BUY same=793, SELL same=572, opposed=0, joint WAIT=1031, scalp-only=0, trend-only=8, active conditional agreement=0.994173.
- USD_CHF/M15: common-ready=709, BUY same=216, SELL same=178, opposed=0, joint WAIT=314, scalp-only=0, trend-only=1, active conditional agreement=0.997468.
- USD_CHF/H1: common-ready=90, BUY same=42, SELL same=12, opposed=0, joint WAIT=36, scalp-only=0, trend-only=0, active conditional agreement=1.000000.
- USD_CHF/H4: common-ready=0, BUY same=0, SELL same=0, opposed=0, joint WAIT=0, scalp-only=0, trend-only=0, active conditional agreement=UNDEFINED.
- USD_JPY/M5: common-ready=2450, BUY same=740, SELL same=600, opposed=0, joint WAIT=1105, scalp-only=0, trend-only=5, active conditional agreement=0.996283.
- USD_JPY/M15: common-ready=831, BUY same=260, SELL same=205, opposed=0, joint WAIT=365, scalp-only=0, trend-only=1, active conditional agreement=0.997854.
- USD_JPY/H1: common-ready=208, BUY same=57, SELL same=52, opposed=0, joint WAIT=99, scalp-only=0, trend-only=0, active conditional agreement=1.000000.
- USD_JPY/H4: common-ready=57, BUY same=18, SELL same=9, opposed=0, joint WAIT=30, scalp-only=0, trend-only=0, active conditional agreement=1.000000.

The complete 360-cell pairwise matrix covers every strategy pair/timeframe/instrument at common eligible decision timestamps, requiring available executable M5 opens, the original session rules and both feature warm-ups. Joint abstention is reported separately and excluded from active-agreement denominators. A zero-signal denominator is undefined, never perfect agreement. Previous-only timing matches are bounded to one native bar. Same-time signal reference prices coincide by construction; actual fill differences and matched trade-R correlations are separately recorded in trade_overlap.json. Correlation is undefined for tiny/constant samples. Identical signals/trades are not independent experiments. Do not delete either operational strategy in this task.

TIV23_RESEARCH_PARTIALLY_VERIFIED. Production remains NO-GO. No new independent archive was acquired. Existing data is PREVIOUSLY_EXAMINED; these diagnostics are exploratory, not independent validation, policy optimisation or proof of future profitability.

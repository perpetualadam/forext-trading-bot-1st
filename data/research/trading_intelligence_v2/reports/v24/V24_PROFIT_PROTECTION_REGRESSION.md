# V2.4 Profit Protection Regression

Operational profit_protection.py is unchanged. Existing TIV2 and MTF
regressions remain required: 67% original TP activation, ATR14*0.5, four-pip
fallback, monotonic ratchet, both sides and JPY pip precision. V24 adds a synthetic
next-open protection endpoint ledger test, which is not a substitute for those
existing source-backed tests. Cost trace is optional and does not change the
protection call, MFE update, pending flag or exit priority. No stop or target
parameter was optimised. Verification results are recorded in test_results.json.

Production remains NO-GO. Research simulation only; the 29-day archive was previously examined.

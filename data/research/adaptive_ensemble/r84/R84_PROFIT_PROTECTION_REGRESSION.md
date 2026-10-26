# R.84 profit-protection regression

`forex_bot/profit_protection.py` was not modified. `test_01` asserts SHA-256 `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f`.

The partial operational close keeps `profit_protection_exit_pips` at 40. The killed partial successor prints `ratchet=40` and `manageable=0`. Its cycle sends no PositionClose and no stop-replacement request. The 67 percent activation, ATR(14), 0.5 multiplier, four-pip fallback, monotonic ratchet, BUY and SELL handling, JPY pip size, original stops, and weekend flattening stay in the unchanged file.

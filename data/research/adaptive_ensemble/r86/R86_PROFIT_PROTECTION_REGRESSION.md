# R.86 Profit Protection Regression

`forex_bot/profit_protection.py` was not edited.

SHA-256 remains `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f`, checked by `test_49` and the baseline hash command.

The 0.67 activation default, ATR multiplier 0.5, four-pip fallback, monotonic ratchet, BUY/SELL handling, JPY pip size, original stops, and weekend flattening were not modified.

The cycle fixture stored `profit_protection_exit_pips` 40 and read it back as 40 after the incomplete-snapshot cycle. The report module has no stop-replacement call. The synthetic broker recorded one `PositionClose`, which was the partial close under test, and no later close.

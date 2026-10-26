# R.83 profit-protection regression

`forex_bot/profit_protection.py` was not modified.

SHA-256, asserted by `test_01`:

`d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f`

The 67 percent activation, ATR(14) simple true range, 0.5 multiplier, four-pip fallback, monotonic ratchet, BUY and SELL handling, JPY pip size, original stop and target, and weekend flattening stay in that file.

`test_08` persists `profit_protection_exit_pips=40` before the partial close, kills the process after the confirmation commit, and the successor prints `ratchet=40`. The row is not manageable. The cycle in the conflicting-snapshot successor sends no close and no stop-replacement request. The worker raises `IsolationBreach` for any OrderCreate or PositionClose beyond the one close already recorded. No TradeCRCDO or OrderReplace sink was added.

# R.82 partial-close profit protection

`forex_bot/profit_protection.py` was not modified.

SHA-256, checked by `test_01_baseline_and_gates` on Windows and Linux:

`d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f`

Parameters left as they are in that file: activation at 67 percent of the original take-profit distance, ATR(14) simple true range, multiplier 0.5, four-pip fallback, and a monotonic ratchet. R.82 did not change original stop-loss or take-profit calculations, weekend flattening, or pip size.

`test_15` calls `update_protected_exit_pips` with max profit 80 and giveback 20 before the 400-unit close. After the close, `profit_protection_exit_pips` is greater than or equal to that value. The position identity is unchanged. The partial close does not replace the trade id.

No TradeCRCDO, OrderReplace, or other stop-modification request was added. The synthetic API used by the restart worker rejects unexpected write types. A quarantined recovery row is not manageable, so the cycle under test does not manage it.

`test_16` checks USD_JPY unit arithmetic only. It does not retune JPY pip size.

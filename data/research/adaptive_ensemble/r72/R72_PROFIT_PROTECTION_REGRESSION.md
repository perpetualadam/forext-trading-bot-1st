# R.72 Profit Protection Regression

`forex_bot/profit_protection.py` SHA-256 remains `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f`.

`forex_bot/trading.py` SHA-256 remains `5ac3981690fe9536edaedfd35a933d17fc37a1e4a77c5c3e9b47517db6300fc7`.

`forex_bot/positions.py` SHA-256 remains `129101e45bafbe0b3359127b3f6e4cf49721a18da1c76301d8d86968218207d5`.

Windows checks, using the existing functions:

| Check | Result |
| --- | --- |
| Trigger percent, ATR period, giveback multiplier, fallback | 0.67, 14, 0.5, 4.0 |
| EUR_USD pip, USD_JPY pip | 0.0001, 0.01 |
| 30-pip original TP, BUY and SELL activation | 20.1 pips |
| ATR 0.0010 giveback | 5.0 pips, source `atr` |
| Missing ATR | 4.0 pips, source `fallback` |
| Later larger ATR | stored exit does not move down |
| R.68 observation | `reconcile_import` with `observation_only` is not permitted |
| R.70 `{}` | `INCOMPLETE` |
| R.70 `{"positions": []}` | `COMPLETE_EMPTY` |
| Friday 2026-10-23 20:50 UTC | `flatten_for_weekend_at` true |
| Sunday 2026-10-25 12:00 UTC | `flatten_for_weekend_at` false |

The R.71 calculation file passed 8 tests. The R.70 suite passed 26 tests. No strategy constant was retuned. The entry block text is still present.

`R72_PROFIT_PROTECTION_UNCHANGED`

`R72_R70_SNAPSHOT_CONTRACT_PRESERVED`

`R72_ENTRY_BLOCK_UNCHANGED`

# R.83 close unit validation

`test_13_closed_unit_contract` calls `apply_transaction_body` on synthetic dicts. These are not OANDA records.

| Case | Result |
| --- | --- |
| 400 of 1000 | `CLOSE_PARTIALLY_CONFIRMED`, remaining 600 |
| 1000 of 1000 | `CLOSE_FULLY_CONFIRMED`, remaining 0 |
| 999 of 1000 | Partial, remaining 1 |
| 0 closed, fill units `-1` | `CLOSE_RECONCILIATION_REQUIRED`, not full |
| -100 closed | `CloseReadError` |
| 1200 | Reconciliation, remaining `None` |
| `nope` | `CloseReadError` |
| Empty units | `CloseReadError` |
| Missing units | `CloseReadError` |
| `400.5` | Partial, remaining `599.5` |
| Same trade id twice | `CloseReadError` before the amounts are added |
| Wrong trade | `CloseReadError` |
| Wrong account | `CloseReadError` |
| Wrong instrument | `CloseReadError` |
| Empty transaction id | `CloseReadError` |
| SELL 400 | Remaining 600 |
| USD_JPY 400 | Confirmed 400 |

No memory removal is performed by this test. No transaction id is invented. A duplicate trade id is rejected rather than summed.

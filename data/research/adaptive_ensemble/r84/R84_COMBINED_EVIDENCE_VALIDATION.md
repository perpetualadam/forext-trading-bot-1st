# R.84 combined evidence validation

Executed by `test_05_wrong_sign_duplicate_and_mixed_evidence`.

| Evidence | Result |
| --- | --- |
| `tradesClosed` only, signs agree | Counted once |
| `tradeReduced` only, signs agree | Counted once |
| Both fields absent | `CloseReadError("missing_closed_trade_details")` |
| Same trade in both fields with the same signed quantity | Counted once. 400 plus a repeated 400 stays 400 |
| Same trade in both fields with different quantities | `CLOSE_RECONCILIATION_REQUIRED`, `contradictory_reduction` |
| Same trade id twice inside `tradesClosed` | `CloseReadError("duplicate_transaction_id")` |
| `tradeReduced` names a different trade | `CLOSE_RECONCILIATION_REQUIRED` |
| `tradeOpened` together with a reduction | `mixed_open_and_reduce` |
| Fill magnitude different from the reduction magnitude | `fill_reduction_mismatch` |
| Unknown extra `clientExtensions` | Ignored. Confirmation still depends on the trade evidence |

The parser does not add the two fields when they describe the same reduction.

# R.72 Protection State Matrix

Position-level results from `interpret_trade_protection` and `collect_broker_protection_evidence`.

| Evidence | Protection | Order state | Exit | Close or delete |
| --- | --- | --- | --- | --- |
| Local SL/TP only, paper or synthetic row | `PROTECTION_UNKNOWN` (`local_reference_not_broker_evidence`) | unknown | unknown | no |
| Open trade, pending stop or TP, identity and units match | `PROTECTION_CONFIRMED` for that side | `ORDER_PENDING_CONFIRMED` | unknown | no |
| Open trade, both sections JSON null | `UNPROTECTED_CONFIRMED` | unknown | unknown | no |
| Open trade, stop key absent | stop `PROTECTION_UNKNOWN` | unknown | unknown | no |
| No trade id, or more than one trade id | `PROTECTION_UNKNOWN` | unknown | no request | no |
| Missing client, account, timeout, exception, null, malformed, non-finite price, bad units | `PROTECTION_UNKNOWN` | unknown | unknown | no |
| Duplicate order id, other trade id, pending plus filling id, unit or direction mismatch | `PROTECTION_CONFLICT` | unknown | unknown | no |
| Cancelled stop | protection unknown | `ORDER_CANCELLED_CONFIRMED` | unknown | no |
| Rejected stop | protection unknown | `ORDER_REJECTED_CONFIRMED` | unknown | no |
| Trade document state `FILLED` with `fillingTransactionID` | protection unknown | `ORDER_FILLED_CONFIRMED` | `EXIT_ATTRIBUTION_UNKNOWN` | no |
| `PARTIALLY_FILLED` | unknown | unknown | unknown | no |
| `CLOSED` and no filled order section | unknown (`broker_trade_closed_without_fill_attribution`) | unknown | unknown | no |
| Observation, reconcile import, unknown kind | `PROTECTION_UNKNOWN` (`management_not_permitted`) | no request | unknown | no |

`STOP_LOSS_FILL_CONFIRMED` and `TAKE_PROFIT_FILL_CONFIRMED` are defined and were not produced by any Windows test. Confirming those requires a transaction body this stage does not fetch.

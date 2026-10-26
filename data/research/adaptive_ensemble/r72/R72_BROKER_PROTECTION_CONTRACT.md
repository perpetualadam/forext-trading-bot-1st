# R.72 Broker Protection Contract

Implemented in `forex_bot/broker_protection.py`.

One record, `ProtectionEvidence` (lines 71–89), carries three dimensions:

| Dimension | Values |
| --- | --- |
| Protection | `PROTECTION_UNKNOWN`, `PROTECTION_CONFIRMED`, `UNPROTECTED_CONFIRMED`, `PROTECTION_CONFLICT` |
| Order lifecycle | `ORDER_PENDING_CONFIRMED`, `ORDER_FILLED_CONFIRMED`, `ORDER_CANCELLED_CONFIRMED`, `ORDER_REJECTED_CONFIRMED`, `ORDER_UNKNOWN` |
| Exit attribution | `STOP_LOSS_FILL_CONFIRMED`, `TAKE_PROFIT_FILL_CONFIRMED`, `EXIT_ATTRIBUTION_UNKNOWN` |

Stop and take-profit each have their own protection and order fields. `protection_state` is the position-level summary.

`ProtectiveOrderEvidence` (lines 56–68) carries instrument, trade id, order id, type, state, `Decimal` price, optional `Decimal` units, transaction id, transaction type, transaction time, and source. Malformed or non-finite prices and units raise `ProtectionReadError` (`_decimal`, lines 158–170). They are not coerced to zero.

`ProtectionEvidence` also carries account scope (`scoped` or `missing`, not the account id), trade ids, evidence source, completeness, collection generation, and uncertainty reason. These flags are always false: `local_prices_are_broker_evidence`, `authorises_close`, `authorises_management`, and `authorises_local_delete`.

## Authority rules

1. Local `stop_loss` and `take_profit` are ignored. A missing protection section stays unknown (`protection_sections_absent`). It is not confirmed protection and it is not confirmed absence.
2. `PROTECTION_CONFIRMED` requires an open trade whose instrument, id, unit sign, and absolute units match the local row, plus a `PENDING` `STOP_LOSS`, `GUARANTEED_STOP_LOSS`, or `TAKE_PROFIT` order whose `tradeID` matches.
3. `UNPROTECTED_CONFIRMED` for a side requires that side's key to be present and JSON null on that complete open trade. Both sides null makes the position-level state `UNPROTECTED_CONFIRMED`. One explicit null and one missing key leaves the position-level state unknown.
4. Direction mismatch, unit mismatch, duplicate order ids, an order linked to another trade, and a pending order that also carries `fillingTransactionID` become `PROTECTION_CONFLICT`.
5. `ORDER_FILLED_CONFIRMED` records that the trade document says the order is filled. Exit attribution stays `EXIT_ATTRIBUTION_UNKNOWN` with reason `fill_reported_without_transaction_body`. The constants `STOP_LOSS_FILL_CONFIRMED` and `TAKE_PROFIT_FILL_CONFIRMED` exist and are not assigned by this reader.
6. A `CLOSED` trade without a filled order section is `broker_trade_closed_without_fill_attribution`. It is not a stop fill and not confirmed absence.
7. Unknown, conflict, and stale results do not grant management, delete a row, or authorise a close.

`R72_BROKER_PROTECTION_MODEL_IMPLEMENTED`

`R72_LOCAL_REFERENCE_NOT_BROKER_PROTECTION`

`R72_INCOMPLETE_EVIDENCE_FAILS_CLOSED`

`R72_CONFIRMED_ABSENCE_REQUIRES_COMPLETE_EVIDENCE`

`R72_PENDING_ORDER_NOT_TREATED_AS_FILL`

`R72_BROKER_FLAT_NOT_TREATED_AS_FILL`

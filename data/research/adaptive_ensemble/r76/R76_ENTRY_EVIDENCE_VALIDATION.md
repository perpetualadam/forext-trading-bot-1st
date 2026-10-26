# R.76 entry evidence validation

Module: `forex_bot/broker_entry_evidence.py`

The classifier returns one of:

- `ENTRY_CONFIRMED_SINGLE_TRADE` with `manageable = True` and reason `trade_opened`
- `ENTRY_CONFIRMED_MULTIPLE_TRADES` / `multiple_opened_trades`
- `ENTRY_REJECTED_CONFIRMED` / `broker_reject_or_cancel` when a reject or cancel transaction is present and the fill is absent
- `ENTRY_PARTIAL_OR_MIXED_EFFECT` / `partial_fill` or `existing_trade_reduced_or_closed`
- `ENTRY_OUTCOME_AMBIGUOUS` / `malformed_response` or `missing_fill_transaction`
- `ENTRY_EVIDENCE_CONFLICT` for account, instrument, client id, direction, opened-unit mismatch, or a conflicting retrieved fill
- `ENTRY_RECONCILIATION_REQUIRED` / `missing_trade_id` or `missing_units`

`record_entry_response` writes that state before any position publish. A confirmed single trade with a null stop or take-profit on the journal row is rewritten to `ENTRY_RECONCILIATION_REQUIRED` / `missing_protection_state`. The stop and take-profit are not read from the current price.

No evidence state calls `PositionClose` or `OrderCreate`. Test 28 records the order id `O-ORDER` on the entry row and the trade id `T-TRADE` on the position. `local_broker_trade_ids` returns `["T-TRADE"]`.

Tests 01 through 15 cover the identity matrix with synthetic bodies.

# R.74 Broker Evidence Recovery

Recovery does not submit a close. Read-only resolution is `resolve_from_retrieved_transaction` (`broker_close_evidence.py` lines 182–223). It applies one transaction body that the caller already holds, through the existing `apply_transaction_body` matcher. It does not call `PositionClose`, `OrderCreate`, or `TradeClose`.

`note_recovery_observation` (lines 161–179) stores an observation string and leaves the confirmation state unchanged.

Rules used:

- No body: state unchanged, observation `no_attributable_transaction`.
- A matching retrieved `ORDER_FILL` may mark full or partial confirmation. It still does not delete the local row by itself.
- A partial result keeps the same operation id, confirmed units, and remainder.
- An open trade observation does not clear an ambiguous row.
- A flat snapshot does not select which operation closed the trade. `account_disappeared_broker_position` returns `retained` unless exactly one fully confirmed journal row matches the current local identity.

The OANDA SDK wrappers already used by this repository are `TransactionDetails` for a known transaction id and `TradeDetails` for a known trade. This stage did not add a time-window search. An empty search was not treated as proof that no request was sent.

`test_flat_snapshot_and_open_trade_do_not_confirm` kept the row after a flat book, recorded `trade_still_open` without leaving `CLOSE_OUTCOME_AMBIGUOUS`, and only then applied a synthetic retrieved transaction. `PositionClose` count stayed 1.

No live or practice OANDA call was made.

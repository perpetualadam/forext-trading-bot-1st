# R.78 ambiguous entry reconciliation

Trace, with no broker connection:

1. `begin_entry_submission` (`entry_journal.py` line 59) commits the reservation and the client-id registry row before any network call.
2. `claim_entry_permit` claims that reservation once.
3. `execute_oanda_market_open` is unchanged. A transport or capture failure marks `ENTRY_OUTCOME_AMBIGUOUS`.
4. `classify_entry_response` classifies one response body. It does not submit.
5. `record_entry_response` commits a verified entry and its position in one transaction, then publishes memory. Ambiguous outcomes are not finalised.
6. `recover_entry_operations` and `execute_startup_sequence` quarantine unresolved entry states. They do not resubmit them.
7. `commit_verified_entry` remains the only finalisation path and was not changed.

New read-only path: `forex_bot/entry_investigation.py`.

`classify_entry_investigation` returns one of `matching_trade_found`, `rejected_order_found`, `conflicting_evidence`, `no_matching_evidence`, `snapshot_incomplete`, or `evidence_unavailable`. Every result has `retry_permitted` false, `delete_permitted` false, and `manageable` false.

`record_entry_investigation` inserts one `entry_investigations` row and then reads the entry outcome again. The tested outcome stayed `ENTRY_OUTCOME_AMBIGUOUS`. A second reservation of the same client id still raises.

Absence of a matching transaction is `no_matching_evidence` with reason `absence_is_not_rejection`. That is not a proof the order was never accepted. Startup does not call the investigation function, so an investigation cannot finish an entry or publish a position.

The investigation does not promote a broker-only or manual trade. `evaluate_durable_row` still quarantines a row whose provenance is not `bot_managed`.

# R.76 broker and local reconciliation

`evaluate_durable_row` (`forex_bot/position_recovery.py` line 290) still requires provenance `bot_managed`, a managed execution kind, complete protection fields, and one broker trade with the same account binding, trade id, direction, and units.

Test coverage:

| Case | Result |
| --- | --- |
| Durable row and matching trade | `RECOVERY_COMPLETED`, position restored (test 41) |
| Single OpenPositions trade id | restored by `load_startup_broker_view` (test 71) |
| Broker-only, manual, unknown | observation, not in `positions` (tests 42–44) |
| Same instrument, different trade id | not promoted; discovery stays observation when no durable row matches |
| Two trade ids and one net | not merged; durable row quarantined (test 72) |
| Wrong account, direction, or units | `evaluate_durable_row` returns the mismatch reason and does not publish |
| `COMPLETE_EMPTY` while a durable row exists | `broker_flat_unattributed`; the row is not deleted |
| `INCOMPLETE` | `RECOVERY_BLOCKED`, `empty_book_is_not_flat` (test 40) |
| Ambiguous entry plus a durable row | `ambiguous_entry`, not published (test 45) |
| Confirmed close awaiting finalisation | existing `awaiting_finalisation` decision; recovery does not delete |

`classify_broker_discovery` (line 436) returns `manageable = False` for every provenance other than the explicit non-discovery marker. A broker-only trade is not copied into `positions`.

`_interpret_open_positions({})` still raises `INCOMPLETE`. `{"positions": []}` remains `COMPLETE_EMPTY` (test 67). `reconciliation.py` was not edited. Its hash is `852a6e2a4da35bce50e68f82cd2e625f25bf36a707a3ad258c3c9d09011a9dbd`.

Historical `test_valid_then_incomplete_then_valid_empty_sequence` still expects a flat snapshot to drop the local live row. The row is retained. That failure is `OBSOLETE_BEHAVIOURAL_EXPECTATION`.

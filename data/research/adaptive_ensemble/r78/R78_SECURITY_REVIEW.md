# R.78 security review

Reviewed against the stop conditions. No stop condition fired.

| Control | Evidence |
| --- | --- |
| Caller cannot override a live owner | another process holding the lock forces `recovery_owner_active` |
| Stale owner cannot publish | `publish_recovered` returns `recovery_fence_lost` |
| Stale owner cannot manage | `live_management_permitted` reads the journal epoch |
| Duplicate client id cannot reserve again | registry and in-flight checks unchanged |
| Ambiguous entry is not resubmitted | investigation sets `retry_permitted` false and does not change the outcome |
| Ambiguous close is not resubmitted | repair writes no close and calls no close function |
| Broker-only trade stays unmanaged | provenance check in `evaluate_durable_row` |
| Partial fill is not a complete open | `manageable` remains false |
| Order id is not a trade id | equal ids return `order_id_is_not_trade_id` |
| Journal failure blocks the repair commit | injected `before_commit` |
| R.75 close guard | R.75 suite 13 passed; close source hashes unchanged |
| R.77 atomic finalisation | `entry_capture.py` and `entry_journal.py` hashes unchanged |
| Recovery gate | `bot_loop.py` hash unchanged and still calls `live_management_permitted` |
| Profit protection | hash `d57dfce0...` unchanged; R.71 8 passed |
| Source gates | four gate hashes unchanged |
| Consumed marker | `e1def82e...`, 10 bytes |
| Live permit | no `one_session.permit` |
| Repair does not enable trading | no permit, no gate edit, no order call |

The new client-id check in `broker_entry_evidence.py` is stricter than R.77. A fill without `clientExtensions.id` and without `clientOrderID` is now a conflict. Existing R.76 and R.77 fixtures include a client id and still passed apart from the schema pin.

Isolation covered the Linux import probe and the test workers. Loopback is the only socket class the harness allows, and the audit recorded no connect attempt.

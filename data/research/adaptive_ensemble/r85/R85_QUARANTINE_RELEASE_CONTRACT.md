# R.85 Quarantine Release Contract

This is a proposed contract. R.85 does not implement it. `position_recovery.py` has no `release_quarantine`. Executed restarts with a 600-unit snapshot, a 1000-unit snapshot, a flat snapshot, and a conflicting snapshot all left `manageable` false.

A future stage may consider a quarantined position manageable only when every row below is satisfied by durable or freshly observed evidence. If any row is not available, the position stays quarantined.

| # | Condition | This stage | Why |
| --- | --- | --- | --- |
| 1 | Current recovery authority | PARTIALLY_AVAILABLE | The epoch and OS lock exist. The lock is released when startup finishes, so it does not cover a later cycle. |
| 2 | Durable position identity | AVAILABLE | Instance id, generation, trade id, account, and instrument are stored. |
| 3 | Durable entry finalisation | PARTIALLY_AVAILABLE | `ENTRY_FINALISED` exists for the entry path. A position persisted only through the close path may have no entry row. |
| 4 | Durable close-operation state | AVAILABLE | The close row and its state are stored. |
| 5 | Consumed close permit | AVAILABLE | `network_permit=1` was read back after restart. |
| 6 | Verified close transaction identity | AVAILABLE | The partial fixture stored `TX-R85`. A second id is now refused. |
| 7 | Confirmed closed quantity | AVAILABLE | Decimal confirmed units on the close row. |
| 8 | Exact remaining quantity | PARTIALLY_AVAILABLE | Journal remaining is stored. It is not broker proof. |
| 9 | Complete broker snapshot | PARTIALLY_AVAILABLE | `COMPLETE_EMPTY` and a non-empty detail map exist. Pagination completion does not. |
| 10 | Broker trade id match | AVAILABLE | Mismatch quarantines. |
| 11 | Account match | AVAILABLE | Mismatch quarantines. |
| 12 | Instrument match | AVAILABLE | A different instrument is not the target. |
| 13 | Direction match | AVAILABLE | Mismatch quarantines. |
| 14 | Snapshot freshness | NOT_AVAILABLE | No timestamp and no watermark. |
| 15 | No unresolved conflicting transactions | PARTIALLY_AVAILABLE | A different transaction id on the same operation is refused. There is no account-wide transaction scan. |
| 16 | No second active owner | PARTIALLY_AVAILABLE | The OS lock excludes a second startup while it is held. It is not held during later publication. |
| 17 | No duplicate in-memory position | PARTIALLY_AVAILABLE | Startup clears its own book. Another live process has a separate book. |
| 18 | Valid risk state | NOT_VERIFIED | Original units remain on the row. Sizing currency is an open R.66 item. |
| 19 | Valid stop-protection state | NOT_VERIFIED | `broker_sl_tp_hit` is not a verified broker stop. |
| 20 | Ratchet preservation | AVAILABLE | The 40-pip value stayed durable. A lower ratchet is refused by the existing persist path. |

Because freshness, pagination, broker-stop evidence, and risk-state evidence are not established, the release condition is not met. The position remains quarantined.

Proposed future rule, not implemented: publish manageable units equal to the journal remainder only when a fresh, complete, same-identity snapshot reports that exact remainder, the close transaction is the only reduction, the ratchet is unchanged, and the publishing process holds the current epoch. Original units would stay on the original field. This stage does not add that field and does not perform that publish.

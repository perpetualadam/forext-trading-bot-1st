# R.85 Full Close Reconciliation

Evidence: executed full close through `run_guarded_live_close`, then real `execute_startup_sequence`. The fill used `tradesClosed` of the full signed quantity. `close_confirmed_live_position` was not called before the snapshot cases, so the journal stayed `CLOSE_FULLY_CONFIRMED` rather than `CLOSE_FINALISED`.

`CLOSE_FULLY_CONFIRMED` means the transaction evidence matched the request. `CLOSE_FINALISED` means local removal was recorded. The snapshot tests did not create a new broker transaction and did not move the row to `CLOSE_FINALISED`.

| Snapshot | Result |
| --- | --- |
| Complete view still showing 1000 | `confirmed_close_not_finalised`, not manageable |
| Complete view showing 600 | `units_mismatch`, not manageable |
| `COMPLETE_EMPTY` | `broker_flat_unattributed`, not manageable |
| `INCOMPLETE` empty | startup blocked |
| `REQUEST_FAILED` | startup blocked |
| `STALE` | startup blocked |
| Wrong trade id | `trade_id_mismatch` among the decisions |

`PositionClose` was counted once. No re-entry `OrderCreate` was recorded. The journal was not rewritten to match the snapshot. An empty complete snapshot did not invent a fill and did not substitute for the existing transaction evidence. It also did not release the position into management, because a flat label is `broker_flat_unattributed` while the durable row still exists.

A stale label is the only freshness signal the evaluator has. The tests supplied that label. They did not prove a snapshot predated the close by a timestamp. That comparison is not available.

The genuine successor and the killed-process successor both left the row at `CLOSE_FULLY_CONFIRMED` when the original owner did not complete a current-epoch finalisation.

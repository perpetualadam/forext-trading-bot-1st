# R.85 Ambiguous Close Reconciliation

Evidence: executed `run_guarded_live_close` whose retrieved transaction had units and neither `tradesClosed` nor `tradeReduced`. The parser returned `missing_closed_trade_details`. The stored state was not `CLOSE_FULLY_CONFIRMED` and not `CLOSE_PARTIALLY_CONFIRMED`. `confirmed_units` stayed null. `network_permit` stayed 1.

| Snapshot after the ambiguous close | Result |
| --- | --- |
| Original 1000 units | quarantined, confirmed units still null |
| Reduced 600 units | quarantined, state not rewritten to partial |
| `COMPLETE_EMPTY` | `broker_flat_unattributed` |
| Missing target trade | not manageable |
| `INCOMPLETE` | startup blocked |
| Wrong trade id | `trade_id_mismatch` |
| `STALE` | startup blocked |

No second `PositionClose` was sent. No transaction id was invented. The difference between the original units and a later snapshot was not stored as confirmed units. Quarantine was not released. The permit was not reset.

The synthetic transaction is not an OANDA timeout on the public network. It is an offline malformed-evidence fixture. The live transport ambiguity remains unverified.

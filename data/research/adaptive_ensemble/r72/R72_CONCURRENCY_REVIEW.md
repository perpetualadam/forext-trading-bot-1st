# R.72 Concurrency Review

TradeDetails is not covered by the R.70 OpenPositions generation. This stage adds a separate in-process counter in `broker_protection.py`.

`_begin` (lines 173–177) increments `_generation` before the request. `_publish` (lines 193–199) writes only when the generation is still current and `_identity_now` (lines 180–190) still sees the same symbol and the same trade-id tuple in `positions`.

| Case | Observed on Windows |
| --- | --- |
| Older success after a newer success | Older result reason `stale_response`. Stored order id stays `NEW`. |
| Newer timeout after a published success | Stored order id stays `KEEP`. The new return is `timeout`. |
| Trade id changed while the request was held | Reason `identity_changed`. Nothing stored. |
| Local row removed and an observation imported while the request was held | Reason `identity_changed`. Observation remains `observation_only`. Nothing stored. |

The counter is process-local. It is not restart-durable. A response without a broker timestamp does not get a wall-clock freshness claim. The lock is not held during the broker call and is not a position-store lock.

Unresolved: two evidence reads for different symbols share one generation, so a newer read of symbol B discards an older in-flight success for symbol A even when A's identity did not change. The last published A record is kept. A crash between read and publish loses the result. The R.70 reconcile report dictionary is still not generation-protected. Those races are recorded for a later stage and were not closed by adding a global position lock.

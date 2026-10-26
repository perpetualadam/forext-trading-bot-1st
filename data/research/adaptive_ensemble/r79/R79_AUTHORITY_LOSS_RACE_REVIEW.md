# R.79 Authority-Loss Race Review

Evidence class: executed tests where noted, otherwise source inspection.

| Scenario | Result |
| --- | --- |
| Authority valid before the cycle | `test_01`. Recovery completed, cycle ran, management true, no write. |
| Authority lost before the cycle | `test_11`. Epoch incremented, original cycle ran, management false, no write. |
| Authority lost after startup and before evaluation | Same test. The cycle body still evaluates an empty symbol list and does not manage. |
| Authority lost before profit protection | Not a separate `apply_profit_protection` call. The live branch in `bot_loop.py` returns at 796–802 when management is false, which is before that call. Source inspection. |
| Authority lost immediately before a write adapter | The adapter calls `live_management_permitted()` on entry. `test_06` covers the false case. A bump followed immediately by `_submit_order_create` was not a separate test. |
| Authority lost while a synthetic read is pending | NOT_VERIFIED. No test paused inside `api.request` for a read and changed the epoch before the call returned. |
| Journal unavailable during evaluation | PARTIAL. `test_14` makes the journal unreadable before startup. A fault armed after a successful startup and during evaluation was not run. |
| Journal corrupt during evaluation | Same partial coverage as the unavailable case. |
| Fencing epoch changes concurrently | `test_05` and `test_11` change it before the next publication or cycle. A change between the check and `api.request` was not interleaved. |
| Another process repairs the claim | R.78 overlapping repair tests passed on Windows and Linux. They were not run inside an in-flight cycle. |
| Process-local recovery state reset | `test_12`. Management false until a new startup. |
| Legacy helper after authority loss | `test_04` places through `recover_managed_book` and management stays false. `publish_recovered` after a stale epoch returns `recovery_fence_lost`. |

The write adapters re-read authority immediately before permit consumption. That closes the gap between the start-of-cycle check and the adapter. It does not close the gap between the adapter check and the socket write. Closing that residual race would require a broker-side idempotency guarantee or a durable compare-and-submit protocol around the HTTP call. OANDA documentation does not provide that guarantee. `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED` remains.

No automatic retry was added after an ambiguous OrderCreate or PositionClose.

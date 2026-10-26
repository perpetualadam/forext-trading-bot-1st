# Process-restart trace

Process A writes the store and exits. The parent waits. Process B starts, the application recovers the row, and the second evaluation blocks.

## FILLED

Process A, PID 820, exited 0. It called `evaluate` and dispatched once to the inert adapter. Order `cid-086196846cdf4a4ba2ed12707ffebd29` was FILLED. The store is `data/research/adaptive_ensemble/r23/stores/filled.json`, SHA-256 `91393e0804234d3ee8cbf08bc3d3e14711f9054cc995fb9ae1e2de18a1277010`. Production eligibility was false.

Process A exited before Process B started. Process B, PID 9832, exited 0. `initialise_application` loaded the store through `read_offline_exec_orders`, `select_rows_for_recovery`, and `ingest_recovery_snapshot`. The recovered status was FILLED and the source was `db_recovery`. Exposure was `exposure_unconfirmed`. The second `evaluate` blocked for that reason before reservation. Inert adapter calls: 0. Real broker calls: 0. PostgreSQL connection: none. No duplicate order.

## UNRESOLVED

Process A, PID 3108, exited 0. It called `evaluate` and dispatched once. Order `cid-10870c09a18248e08d9f9018452fa07c` was UNRESOLVED after an ambiguous inert result. The store is `data/research/adaptive_ensemble/r23/stores/ambiguous.json`, SHA-256 `503ff813487288aff6e1bdf05a1d5f30585af1817ac26094a33a52a520b3daf0`. Metadata records `ambiguous_broker_outcome` and `exposure_safety` UNCONFIRMED.

Process A exited before Process B started. Process B, PID 14156, exited 0. Recovery used the same startup functions. The recovered status was UNRESOLVED and the source was `db_recovery`. The second `evaluate` blocked on `exposure_unconfirmed` before reservation. Inert adapter calls: 0. Real broker calls: 0. PostgreSQL connection: none. No duplicate order.

The four process IDs are distinct. Network and DNS successes were zero: each child raises on a socket or name lookup, and each child exited 0. The parent barrier recorded 3 blocked attempts and 1 dotenv stub.

# R.73 Single Flight and Idempotency

`_reserve` and `_begin_submit` run under one `threading.Lock`. The first thread inserts `CLOSE_PREPARED` and then moves it to `CLOSE_SUBMITTING` before the HTTP call. A second thread for the same symbol receives the existing operation and does not call `PositionClose`.

The operation id is allocated once. A timeout does not allocate another id.

`declare_process_restart` keeps unresolved operations in a second in-memory map and marks them `restart_unresolved`. A later reserve is refused. Nothing is written to disk or PostgreSQL. An operating-system restart drops both maps.

`RESTART_DURABLE_IDEMPOTENCY_NOT_IMPLEMENTED`

`BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`

The 30-second profit-protection cooldown is unchanged and is not treated as an idempotency key.

`R73_SINGLE_FLIGHT_IMPLEMENTED`

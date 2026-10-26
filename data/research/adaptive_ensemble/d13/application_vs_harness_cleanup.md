# Application cleanup and harness cleanup

`_enter` in the D.12 runner, reused by D.13, records the lifespan snapshot first. That snapshot includes cleanup errors, connection state, worker liveness, and pending owned tasks.

Harness cleanup is recorded afterward as `harness` from thread containment and `harness_closed` from closing fake connections. Those steps are not counted as application cleanup.

For an incomplete stop, the application snapshot shows the worker still alive, the connection still open, pending tasks at 0, and `D12-STOP-01` in the cleanup list. The harness then releases the fake poll and joins the worker.

For the repeated lifespan, lifespan C is snapshotted inside the context after its first poll, before the context exit stops that new worker.

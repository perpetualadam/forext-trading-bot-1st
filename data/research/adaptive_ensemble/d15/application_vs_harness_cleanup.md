# Application cleanup and harness cleanup

The lifespan snapshot used by the assertions is taken before the harness joins the worker and closes fake database objects.

Application cleanup observed:

- A normal shutdown leaves `connection_open` true and the worker not alive.
- An incomplete stop leaves the worker alive, the stop event set, the connection open, and `D12-STOP-01` in cleanup diagnostics.
- A broker startup failure leaves the connection closed and does not add `D12-STOP-01`.
- Owned asyncio tasks were done after the lifespan child returned.

Harness cleanup observed:

- After the database schedules, the harness close leaves `open_connections` and `open_cursors` empty.
- The harness joins a worker that the application intentionally left tracked.
- That join is not counted as application shutdown.

An intentionally retained connection is not a leak. A tracked worker that is still alive is not treated as terminated.

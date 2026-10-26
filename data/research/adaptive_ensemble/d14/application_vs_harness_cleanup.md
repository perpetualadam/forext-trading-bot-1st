# Application cleanup and harness cleanup

Lifespan snapshots are taken by the existing D.12 helper before harness containment. That snapshot includes cleanup errors, the connection, the worker, and pending tasks.

Harness join and fake-connection close are stored afterward. They are not counted as application cleanup.

On refusal, the application snapshot shows the original worker alive, the stop event set, the connection reused, and the `D12-START-01` warning already emitted. The harness later releases the fake poll and joins the worker.

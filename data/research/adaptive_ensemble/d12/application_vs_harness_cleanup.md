# Application cleanup versus harness cleanup

On the blocked lifespan, the application snapshot showed a live stored worker, an empty cleanup-error list, a retained database connection, and no pending owned tasks. That snapshot was taken before the fake poll was released.

The harness then set the release event and joined the worker. That exit is harness cleanup.

On the repeated-lifespan run, lifespan B returned while the original worker was still alive. The poll release that let the worker exit happened after that snapshot and before lifespan C.

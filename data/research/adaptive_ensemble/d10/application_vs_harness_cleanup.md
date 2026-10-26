# Application cleanup versus harness cleanup

The snapshot is taken after the production function returns and before the harness releases the fake poll, unblocks a query, joins a thread, or closes a connection.

| Scenario | Application result | Harness afterwards |
| --- | --- | --- |
| Normal stop | Thread 19340 was dead. Elapsed 0.0002s. | No live thread to join. |
| Blocked poll stop | Thread 16048 was alive. Stored reference was already cleared. Connection 1 was still open. | Not yet involved. |
| Release after that stop | Application release closed connection 1. Thread 16048 then queried and published connection 2, then the production loop saw the stop event and exited. | Harness closed connection 2. It did not join a live thread because the worker had already exited. |
| Locked query | Application release did not finish during the 0.3s observation. It finished after the query was released and closed the connection. Thread 19876 was still alive. | Harness then stopped and joined 19876. |
| Restart overlap | Application start left 13880 and 17184 alive and cleared the stop event. | Harness set the stop event, released the fake poll, and joined both. |
| Lifespan blocked shutdown | `lifespan` returned with thread 3836 alive, four tasks finished, connection still held, and `cleanup_errors` empty. | Harness released the fake poll and joined 3836, then closed the connection the success path intentionally kept. |
| Lifespan broker failure | Application closed the connection. No Telegram thread. | Harness closed nothing. |
| Release close failure | Application cleared the global, recorded `RuntimeError`, and left the object open because `close` raised. | Harness closed that object. `harness_closed` 1. |
| Successful lifespan | Application cancelled all four tasks. Pending 0. Connection kept. Fast poller had exited. | Harness closed the kept connection. `harness_cancelled` 0. |

Harness joins, harness closes, and the child process ending are not counted as application cleanup. Threads 16048, 13880, and 3836 were alive when the application function returned.

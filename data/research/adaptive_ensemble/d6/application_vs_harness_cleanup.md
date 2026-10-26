# Stage D.6 application cleanup versus harness cleanup

The runner records connection `close_calls`, whether `_pg_conn` is still held, and which tasks are still pending immediately after `lifespan` returns. Only then does it cancel pending tasks and close fake connections that are still open.

| Case | Application | Harness afterwards |
| --- | --- | --- |
| baseline, account, reconcile, db_connect | 4 tasks cancelled by the application | 0 task cancels. The success-path connection is still open and is closed by the harness so the next case can reconnect. |
| db_cursor, db_execute, db_commit | startup continues and the application cancels tasks; `close_calls` stays 0 and the global is cleared | harness closes the abandoned connection |
| broker, before_tasks | exception escapes; no tasks exist; connection stays held and unclosed | harness closes that connection |
| after_first, later_task, before_yield, repeat_first | exception escapes; 1, 3, or 4 tasks remain pending; application cancelled none | harness cancels those tasks and closes the connection |
| shutdown_stop | yield happened; stop raises; 4 tasks remain | harness cancels 4 |
| await_health | yield happened; health await raises; 3 tasks remain | harness cancels 3 |
| repeat_second | application cancels 4 tasks | harness closes the retained connection only |

A non-zero harness count is not an application pass. Those rows are the cleanup defects.

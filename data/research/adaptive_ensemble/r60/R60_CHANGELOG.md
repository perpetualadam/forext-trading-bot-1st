# R.60 Changelog

R.59 files were not modified. Their hashes still match archive `2652508e3011d86c59c97e1ce65aebe9b29b6392e5264defe78957369f441d63`. R.60 is a separate copy under `data\research\adaptive_ensemble\r60\`.

`live_session_gate.py` and `metadata_extract.py` are byte-identical to R.59. The other modules use `r60_` loader-cache names so this tree does not alias the preserved `r59_` modules. Protocol strings such as `r59.metadata.1`, `r59.one-get.1`, and `r59-` session ids are unchanged. The loader prefix is an isolation change with no protocol effect.

## Cleanup releases read handles while a child is alive

Original defect: `ChildTracker.cleanup` skipped every pipe close when `poll()` stayed `None`. That avoided the Windows stdin flush stall and also left stdout and stderr open, with a reader still attached.

Reproduction: fake processes whose `kill()` raises `PermissionError` or `OSError`, or whose `kill()` does nothing and whose `wait()` raises `TimeoutExpired`. Before the change, those read handles stayed open. The R.59 measurement that stdin close can block for 29.867 seconds is unchanged and is why stdin is still withheld.

Modified function: `ChildTracker.cleanup`.

Behaviour: after the bounded kill and wait attempts, stdin is closed only when `poll()` is not `None`. Stdout and stderr are closed whether or not the child has exited. A surviving child is still reported with `child_alive` true.

Regression: `test_permission_error_does_not_report_a_survivor_reaped`, `test_oserror_on_kill_leaves_the_child_alive`, `test_wait_timeout_and_surviving_child_stay_alive`.

Compatibility: a child that is still alive can see its stdout pipe close during failed termination. The current worker is already being killed on that path. Stdin behaviour matches R.59: it is not closed while the child is alive.

## `children_started` counts processes that were created

Original defect: `_execute` set `children_started` to 1 before `Popen`. A startup deadline could report a child that did not exist, and a real-mode record could have counted an attempt that never reached a process.

Reproduction: `_spawn` called with `deadline_at` already exhausted. `Popen` must not run. The R.59 copy would still have carried `children_started` 1 because that assignment happened before the call.

Modified function: `_execute`.

Behaviour: `children_started` is `len(tracker.procs)` after cleanup. The pre-spawn deadline reports 0, `child_alive` false, `child_terminated` false, and `SESSION_DEADLINE`. A process that was added still counts as 1, including `fault_at=after_spawn` paths that fail after `Popen`.

Regression: `test_session_deadline_during_startup_starts_no_false_child`.

Compatibility: records for a session that dies before `Popen` now say zero children. Sessions that start the worker are unchanged. `child_terminated` stays false on this path because no child was killed.

## `communicate()` does not flush a closed stdin

Original defect: the acknowledgement writer closes stdin, then the parent calls `Popen.communicate()`. CPython 3.12 on Ubuntu flushes that stream and raises `ValueError: flush of closed file`. The exception became `SESSION_FAILED`, so a completed harness, a malformed result, and a request timeout lost their classifications. Windows CPython 3.13.5 did not raise.

Reproduction: the preserved R.59 suite on Ubuntu 24.04.3 / WSL2, Python 3.12.3, failed `test_harness_session_keeps_secrets_and_raw_bodies_out_of_the_log`, `test_timeout_and_spawn_fault_reap_the_child`, `test_overall_deadline_bounds_every_wait`, and `test_malformed_exit_and_cleanup_failures_stay_incomplete`. A direct R.60 run printed `ValueError('flush of closed file')` before this change. After the change, the R.60 Linux suite passed 19 tests.

Modified function: `_spawn`, immediately before `communicate()`.

Behaviour: if stdin is already closed, the handle is dropped before `communicate()`. The closed pipe is not flushed again. Stdout and stderr are still read. The acknowledgement write and its close still finish inside `_ipc_send` before this point.

Regression: `test_closed_stdin_is_not_flushed_again_by_communicate`. The fake raises `ValueError('flush of closed file')` when stdin is still attached. The real worker tests on Ubuntu cover the same path.

Compatibility: Windows behaviour of a successful harness stays `NONE` / `SESSION_INCOMPLETE`. Linux classifications now match that contract. R.59 itself was not patched.

## Changes that were considered and not made

`Popen` was not moved onto a deadline thread. No hung creation was observed, and abandoning a late creation would leave an untracked child.

`HOME`, `LANG`, and `LD_LIBRARY_PATH` were not added. The worker started on this Windows host and on this WSL2 host without them.

A process-group or Windows job kill was not added. The worker creates no descendants. Both hosts showed that a synthetic grandchild survives `kill()` of its parent. The test stops that grandchild. The supervisor does not claim it was reaped.

The supervisor-thread close of a full pipe was not restored. R.59 measured that close at 29.867 seconds.

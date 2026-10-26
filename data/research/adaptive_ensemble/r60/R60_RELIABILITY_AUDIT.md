# R.60 Reliability Audit

Offline subprocess reliability review of the preserved R.59 one-GET diagnostic. R.60 does not enable a broker connection, a permit, or production trading.

`REAL_NETWORK_EXECUTION_NOT_TESTED`

Production trading remains NO-GO.

## R.59 baseline

The R.59 tree was hashed before any R.60 edit. All nine files matched the recorded archive hashes. The verified archive remains:

- Path: `data\research\adaptive_ensemble\r59\R59_SOURCE_REVIEW.zip`
- Size: 27601 bytes
- SHA-256: `2652508e3011d86c59c97e1ce65aebe9b29b6392e5264defe78957369f441d63`

Phase A command, from the project root, before the R.60 copy existed:

`python -B -m pytest -p no:cacheprovider --noconftest data\research\adaptive_ensemble\r59\test_r59_offline.py -q --tb=line`

Result: 13 passed, 0 failed, 7.76 seconds. Windows Python 3.13.5, pytest 8.4.1.

The same command after R.60 was finished: 13 passed, 0 failed, 7.66 seconds. The nine R.59 file hashes were unchanged.

Preserved R.59 behaviour that R.60 keeps:

- Source gate `REAL_SESSION_SOURCE_ENABLEMENT = False`.
- R.56 source gate false, `one_session.consumed` present, `one_session.permit` absent.
- One monotonic `deadline_at` for startup, readiness, IPC writes, the capability acknowledgement, and the worker-response wait.
- Kill, then a bounded wait, then stdin close only after `poll()` shows the child has exited.
- A full-pipe deadline returns `SESSION_DEADLINE` and `SESSION_INCOMPLETE`.
- Empty worker stdout and a broken IPC write are `CHILD_CRASHED`.
- Bad worker JSON is `MALFORMED_CHILD_RESULT`.
- A harness result with error `NONE` stays `SESSION_INCOMPLETE` because a real broker response was not received.

## Subprocess lifecycle

The parent is `diagnostic_supervisor.py`. It starts one child with `subprocess.Popen`, stdin, stdout, and stderr pipes, `child_env()`, and the R.60 directory as the working directory. The executable is `sys.executable` and the worker path is absolute.

`_ipc_send` writes and flushes on a daemon thread. The supervisor joins that thread only for the time remaining until `deadline_at`. If the thread is still alive, the function returns `deadline` and does not close, flush, or join again on the supervisor thread. The caller then reaps the child before an acknowledgement or a result read.

`_reap` kills the child when `poll()` is `None`, joins a reader for at most 1 second, then `wait(timeout=5)`. A wait failure kills once more and waits at most 5 seconds. `PermissionError` and other `OSError` values from `kill()` are caught. `poll()` after those waits decides the result. `True` means the child is still alive. Stdin is closed only when `poll()` is not `None`.

`ChildTracker.cleanup` repeats that kill and wait sequence. In the R.60 copy it closes stdout and stderr even when the child is still alive, and it still refuses to close stdin while `poll()` is `None`. `_execute` always runs cleanup in `finally`, then sets `child_alive` from a fresh `poll()`. If that `poll()` raises, `child_alive` is set true.

A successful `kill()` is not treated as an exit. A surviving child keeps `child_alive` true. Session completion also requires a real broker response, which this harness does not produce.

The worker process does not create subprocesses. A separate fault test starts a parent that does create a grandchild. Cleanup of the tracked parent leaves the grandchild running on both Windows and Linux. The test then stops that grandchild. The supervisor has no field that reports the grandchild as reaped.

## Deadline and cleanup bounds

`deadline_at` is set once, to `started + session_deadline`. Stage waits use the lesser of the remaining session time and the request deadline. The request cap while session time remains is `CHILD_TERMINATED`. Session expiry is `SESSION_DEADLINE` and `SESSION_INCOMPLETE`.

The session deadline does not include process cleanup. After the deadline has already been reached, one tracked child can add this emergency allowance when `wait()` times out:

| Step | Bound |
| --- | --- |
| Reader join inside `_reap` | 1 second |
| First `_reap` wait | 5 seconds |
| Retry `_reap` wait | 5 seconds |
| First cleanup wait | 5 seconds |
| Retry cleanup wait | 5 seconds |
| Emergency total | 21 seconds |

A kill that actually ends the child makes `wait()` return immediately, so the observed addition is a scheduler delay rather than 21 seconds. The real-pipe regression on Windows returned in under 1 second of driver time with a 0.4 second session deadline.

Wall-clock expectations:

| Path | Classification | Expected duration |
| --- | --- | --- |
| Deadline already exhausted before `Popen` | `SESSION_DEADLINE`, `children_started` 0, `child_alive` false | Returns without a 5 second wait |
| IPC write still blocked at the deadline, kill succeeds | `SESSION_DEADLINE`, `child_alive` false | Session deadline, then a short reap |
| IPC write still blocked, kill fails and `wait()` times out | `SESSION_DEADLINE`, `child_alive` true | Session deadline plus up to 21 seconds |
| Ready line not received in the remaining session, kill succeeds | `SESSION_DEADLINE`, `child_alive` false | Remaining session time, plus up to 1 second of reader join, then a short reap |
| Request cap reached while session time remains | `CHILD_TERMINATED` | Request deadline, then reap and cleanup |
| Broken pipe, missing worker, or empty stdout | `CHILD_CRASHED` | Process exit plus a short reap |
| Malformed worker JSON after a completed acknowledgement | `MALFORMED_CHILD_RESULT` | Protocol exchange, inside the session deadline |
| Cleanup raises after an otherwise clean harness result | `CHILD_CLEANUP_FAILED` | The session, then the cleanup allowance |
| Harness protocol completes | `NONE`, `SESSION_INCOMPLETE`, `record_persisted` true | The worker runtime, inside the deadlines |

`subprocess.Popen` itself is not wrapped by `deadline_at`. No hung `Popen` was reproduced on either host, so R.60 does not abandon process creation on a side thread. That operation can still block before the session deadline applies.

## Defects

Three defects were supported by execution or by a direct lifecycle test. They are corrected in the R.60 copy. The R.59 files were not edited.

1. Cleanup skipped stdout and stderr when the child was still alive. The `continue` existed so a full stdin pipe would not be closed on the supervisor thread. That also leaked the read handles and left a blocked reader attached. R.60 closes the read ends in every case and closes stdin only after `poll()` shows the child has exited. Fault tests for `PermissionError`, `OSError`, a no-op kill, and a wait timeout observe `child_alive` true, stdin still open, and stdout and stderr closed.

2. `children_started` was set to 1 before `Popen`. A deadline that expired inside startup could report a child that had never been created. R.60 sets `children_started` from the tracker after cleanup. The pre-spawn deadline test reports 0 and does not call `Popen`.

3. Linux CPython 3.12 raises `ValueError: flush of closed file` from `Popen.communicate()` when the acknowledgement writer has already closed stdin. On this Windows host, Python 3.13.5 completed the same path. The Linux failure turned a finished harness, a malformed result, and a request timeout into `SESSION_FAILED`. R.60 drops the already-closed stdin handle before `communicate()`. A Windows fake that raises the same `ValueError` unless stdin is detached returns `MALFORMED_CHILD_RESULT`. The Ubuntu run then passed the real worker tests.

The R.59 close-before-kill stall is not present in this copy. The real-pipe test still kills a non-reading child before any supervisor-thread close, inside an 8 second outer process.

## Windows and Linux

Windows 11 10.0.26300, Python 3.13.5, pytest 8.4.1: the R.59 suite and the R.60 suite passed. Pipe buffering, `kill()`, `wait()`, and the closed-stdin path were executed, not simulated.

Ubuntu 24.04.3 LTS under WSL2, kernel `6.6.87.2-microsoft-standard-WSL2`, Python 3.12.3, pytest 9.1.1: the R.60 suite passed, including the real pipe, the grandchild, and the worker protocol. This is that WSL2 host, not a second physical distribution.

The same Ubuntu interpreter running the preserved R.59 suite: 4 failed, 9 passed, 6.01 seconds. The failures are the harness completion, request-timeout, overall-deadline, and malformed-result tests. They are the `communicate()` flush defect above. R.59 was left unchanged. Its Windows baseline still passes.

`child_env()` passes `SYSTEMROOT`, `SYSTEMDRIVE`, `WINDIR`, `COMSPEC`, `PATH`, `PATHEXT`, `TEMP`, and `TMP`, plus the Python UTF-8 and unbuffered flags. It does not pass `HOME`, `LANG`, or `LD_LIBRARY_PATH`. The worker still started on this Windows host and on this WSL2 host. No environment variable was added.

`Popen` does not create a new process group. `kill()` is `TerminateProcess` on Windows and `SIGKILL` on Linux. Neither reaps a grandchild. Both hosts showed the grandchild still alive after the parent was reaped.

## Resource leaks

A child that exits has stdin, stdout, and stderr closed by cleanup. A child that survives has stdout and stderr closed and stdin left open. The open stdin is the retained handle that avoids the measured Windows flush stall. The blocked writer is a daemon. It is not joined past the deadline. If the kill succeeds, the write unblocks. If the kill fails, that thread and the IPC frame remain until the child reads or the parent process exits.

Three successful harness sessions and five deadline sessions on Windows left `child_alive` false and did not increase the live thread count by more than one. The Linux repeats did the same.

The grandchild test does not leave the grandchild running. The test process stops it after proving cleanup did not.

## Security invariants

Checked after the suites:

- R.60 and R.59 `REAL_SESSION_SOURCE_ENABLEMENT = False`.
- R.56 `REAL_SESSION_SOURCE_ENABLEMENT = False`.
- R.56 `one_session.consumed` is present. `one_session.permit` is absent.
- R.60 has no `real_activation` directory and no permit.
- `run_real_session` raises `REAL_OANDA_SESSION_NOT_AUTHORISED` before a prompt.
- Parent socket `create_connection` and `connect` are patched to raise in the suite.
- Records and saved JSON were checked for the synthetic account, the synthetic token, `Bearer`, the raw-body marker, and the pipe padding.
- Source files do not reference `forex_bot`, `load_dotenv`, `import requests`, `import httpx`, or `main.py`.
- The worker source does not start a subprocess.

No `.env` file was read. No OANDA call was made. No order path was added.

The R.56 check reads files outside the R.60 archive. If those files are absent, that test fails closed.

## Unresolved risks

- `Popen` can still block before the session deadline applies. It was not wrapped, because abandoning a late `Popen` would create an untracked child.
- A child that survives `kill()` keeps the daemon writer and the unread IPC frame until the child or the parent exits. Closing stdin on the supervisor thread is the operation that blocked for 29.867 seconds in R.59.
- Cleanup does not kill descendants. The current worker creates none. A future worker that did would leave them untracked, and `child_alive` would describe only the direct child.
- The early error path can still close stdin on the supervisor thread after a completed short write. That is not the full-pipe path, and no stall was reproduced there.
- The 21 second cleanup allowance is a cap on the explicit waits. It is not part of the 15 second session deadline.
- Linux evidence is this WSL2 Ubuntu host. It is real Linux process behaviour on that kernel. It is not a bare-metal run and not a second distribution.

## Gate

`R60_OFFLINE_GATE_PASS`

Windows and this WSL2 Linux host both passed the R.60 suite. The preserved R.59 Windows baseline passed and its bytes are unchanged. Cleanup past the session deadline is stated as a separate allowance. A child that is still alive is reported alive.

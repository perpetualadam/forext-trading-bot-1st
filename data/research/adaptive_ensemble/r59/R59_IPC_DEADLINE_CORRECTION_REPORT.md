# R.59 IPC Deadline Correction

**REAL_NETWORK_EXECUTION_NOT_TESTED**

Production trading remains NO-GO. This correction does not enable the R.59 gate, create a permit, or open a broker connection.

## Root cause

`_ipc_send` wrote the IPC frame on a daemon thread and joined that thread for the time left on the one monotonic session deadline. When the join expired, the supervisor thread called `stream.close()` before `_reap` could kill the child.

On Windows, `BufferedWriter.close()` flushes. A flush of a full pipe blocks until the child reads or exits. The investigation measured that close at **29.867 seconds** while the child was still alive. Killing the child first released the blocked write and the later close in about **0.001 seconds**.

`ChildTracker.cleanup` had the same order: it closed stdin before `kill`. On this failure path that close could run while the writer thread was still blocked.

## Source changes

Only `diagnostic_supervisor.py` and `test_r59_offline.py` changed.

`_ipc_send` still starts one daemon writer and joins it only for the remaining session time. If that thread is still alive, the function returns `deadline` and does not close, flush, or join again. The caller in `_spawn` already maps that status to `SESSION_DEADLINE` and calls `_reap` before any capability acknowledgement or worker result is accepted. A harness session never reaches `HTTPSConnection` on this path. A real session is still refused by the source gate before a worker is authorised to open a socket.

`_reap` and `ChildTracker.cleanup` now kill the child, then wait at most 5 seconds, then kill and wait at most 5 seconds again. Stdin is closed only after `poll()` shows the child has exited. A live full pipe is not flushed. Reader-thread cleanup stays a 1 second join.

Broken-pipe and empty-output results are unchanged: the writer thread still swallows the exception and returns `broken`, and the caller still records `CHILD_CRASHED` with `SESSION_INCOMPLETE`. Exception text and the frame are not stored. Atomic `os.replace` persistence is unchanged.

## Before and after

| | Before | After |
| --- | --- | --- |
| Timed-out IPC write | Caller closes the pipe, then would reap | Caller returns `deadline` and reaps |
| Close of a full pipe | Blocked 29.867 seconds until the child exited | Not performed while the child is alive |
| Child termination | Not reached during the blocked close | `kill`, then bounded `wait`, then close |
| Session record | `SESSION_DEADLINE` was delayed by the close | `SESSION_DEADLINE` and `SESSION_INCOMPLETE` as soon as the reap finishes |
| Next stage | Blocked close prevented the reap | No capability acknowledgement and no network call |

## Regression test

`test_real_pipe_deadline_kills_before_close` starts a separate Python process with an 8 second timeout, so a return of the 29 second stall fails the test instead of hanging pytest.

That process loads the real supervisor, replaces `Popen` with a local `sleep 60` child that does not read stdin, and appends 256 KiB of `X` bytes to the real IPC frame. The session deadline is 0.4 seconds. The child would not exit for 60 seconds, so the old close-before-kill path cannot finish inside the 8 second bound. The corrected path must finish with `SESSION_DEADLINE`, `SESSION_INCOMPLETE`, and `child_alive` false, in under 4 seconds of wall time and under 3 seconds inside the driver. The saved record must not contain the synthetic account id, the synthetic token, `Bearer`, or the pipe padding.

## Commands and results

Working directory: `C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st`.

Python 3.13.5. pytest 8.4.1.

The real-pipe test, five times:

```text
python -B -m pytest -p no:cacheprovider --noconftest data\research\adaptive_ensemble\r59\test_r59_offline.py -q --tb=line -k test_real_pipe_deadline_kills_before_close
```

Each run: **1 passed, 12 deselected**, in 0.66, 0.65, 0.66, 0.65, 0.64, and 0.64 seconds. No hang.

The full suite:

```text
python -B -m pytest -p no:cacheprovider --noconftest data\research\adaptive_ensemble\r59\test_r59_offline.py -q --tb=line
```

**13 passed, 0 failed, 7.68 seconds.** The original 12 tests passed with the new regression.

## Worker termination

The driver child is `python -c "import time; time.sleep(60)"` with a real stdin pipe. After the 0.4 second deadline, `_reap` kills it and waits. The returned record has `child_alive` false. The outer process exited 0 well below 4 seconds, which is only possible if that child was reaped rather than left until its 60 second sleep ended.

## Security invariants

| Check | Result |
| --- | --- |
| R.59 gate | `REAL_SESSION_SOURCE_ENABLEMENT = False` |
| R.59 permit | `r59\real_activation` does not exist |
| R.56 gate | line 20 remains `REAL_SESSION_SOURCE_ENABLEMENT = False` |
| R.56 permit | `one_session.consumed` is present. `one_session.permit` is absent |
| Broker and orders | No socket was opened. The regression child is a local sleep process |
| Record contents | The regression record excludes the synthetic account id, token, bearer header, and pipe padding |
| Persistence | The atomic replace path was not edited. The earlier persistence tests passed in the suite |

## Remaining risk

If `kill` fails and the child is still alive after both 5 second waits, stdin is left open. That avoids an unbounded flush. It does not by itself clear a writer thread blocked in the kernel. That case did not occur in the five regression runs.

The early worker-response path still closes stdin after a completed short write, before its bounded wait. That write has already finished, so it is not the full-pipe stall.

The in-memory blocked-stream tests remain. They do not replace this real-pipe test.

## SHA-256 of the nine Python files

| File | SHA-256 |
| --- | --- |
| `credential_ipc.py` | `684668340ead0b4770a1793469482664c198cc721646083579c6b17d9f3d22e7` |
| `diagnostic_supervisor.py` | `d49ce8c042b374e2a1a15c7b4807fc78b225fad79175043d95cab7b4f005e822` |
| `diagnostic_worker.py` | `b0806ad27382a323601207859088c90837a5b11042035ded5deb8a70e4fa2adc` |
| `live_session_gate.py` | `2378037d15e4346edf3c421ef24b791e5993f00ade7f9ea9a1b3c2f837e74ab2` |
| `metadata_extract.py` | `259b9ec4dec03eda81cb9c9713d954ae694695cbfc04c4f8385cef73b50468ab` |
| `one_session_activation.py` | `d15778612b8bd97c65e3a826779fbbf46758f1439c3b4202968749043c6b8d90` |
| `real_session_entry.py` | `d73bccbfab02a2105969f22d68454f960240f5c2a32a5958311423cb21211e80` |
| `restricted_live_transport.py` | `d5ae2ae8bffeb07fd7c601f201a2523b20dc8023c1f20619bffafe988cf568ee` |
| `test_r59_offline.py` | `4800fc7bc70bce4a460ad07b45827be0cae0a012ef2da923614952be6ceffbb2` |

The regression lives in `test_r59_offline.py`. There is no tenth Python file.

## Source archive

`data\research\adaptive_ensemble\r59\R59_SOURCE_REVIEW.zip`

Size `27601` bytes. SHA-256 `2652508e3011d86c59c97e1ce65aebe9b29b6392e5264defe78957369f441d63`.

The archive has exactly these nine members, each under `data/research/adaptive_ensemble/r59/`, and each member matches the table above. It does not contain this report, credentials, `.env`, or a permit.

## Final offline gate

**`R59_OFFLINE_GATE_PASS`**

The original 12 tests and the new real-pipe regression passed, including five repeated runs of the regression. A timed-out IPC write now returns the deadline and the child is killed before stdin is closed.

This pass is not permission to enable the R.59 gate, call OANDA, or run production trading.

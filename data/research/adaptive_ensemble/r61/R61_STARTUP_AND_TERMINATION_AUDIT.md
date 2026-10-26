# R.61 Startup and Termination Audit

Offline hardening of process startup and cleanup. R.59 and R.60 were not modified. No broker connection, permit, or production trading path was added.

`REAL_NETWORK_EXECUTION_NOT_TESTED`

Production trading remains NO-GO.

## Baseline verification

R.60 archive `data\research\adaptive_ensemble\r60\R60_SOURCE_REVIEW.zip` is 27472 bytes, SHA-256 `4d2c490b35fa648a09acc3af0c7f655f24703cda34c85fd259bb25e3a0e6d53d`. All nine R.60 source hashes matched `R60_TEST_REPORT.md` before and after this stage.

R.60 command, from the project root, before any R.61 file was written:

`python -B -m pytest -p no:cacheprovider --noconftest data\research\adaptive_ensemble\r60\test_r60_offline.py -q --tb=line`

19 collected, 19 passed, 0 failed, 8.06 seconds. The same command after R.61: 19 passed in 8.01 seconds.

Windows 11 10.0.26300, Python 3.13.5, pytest 8.4.1, `C:\Python313\python.exe`.

R.60, R.61, and R.56 source gates contain `REAL_SESSION_SOURCE_ENABLEMENT = False`. R.56 `one_session.consumed` stayed present at 10 bytes, SHA-256 `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c`. `one_session.permit` stayed absent.

## Blocking startup

From `run_harness_session` to `Popen` returning, the parent confirms the harness phrase, builds one capability, builds one IPC frame, and then calls `subprocess.Popen` on the supervisor thread.

Before R.61, the monotonic deadline was checked at the start of `_spawn` and was not checked again after the frame was built. In-process work after that check could pass the deadline and still create a process. R.61 checks `deadline_at` again immediately before `Popen`. If the deadline has already passed, no process is created, `children_started` is 0, and the classification is `SESSION_DEADLINE`.

`Popen` itself remains synchronous. A call that blocks inside process creation is outside the session deadline. The supervisor does not put `Popen` on a daemon thread. That design was rejected because the thread could return at the deadline while the operating system was still creating an untracked process.

The limitation is demonstrated, not removed. `test_blocked_popen_is_not_interrupted_by_the_session_deadline` runs a driver whose `Popen` sleeps for 30 seconds and creates no child. The session deadline is 0.25 seconds. An outer process waits until the driver has entered that sleep, waits another 0.5 seconds, observes that the driver is still alive, and then kills the driver. The outer sequence stays under 8 seconds. The test does not claim that startup is bounded.

Resources before `Popen` returns are the in-memory frame and the capability. No OS process exists yet. After `Popen` returns, the `Popen` object is registered on `ChildTracker` before any IPC write. If `add` raises, the object is appended directly so `finally` cleanup still owns it. If that append also fails, `_release_untracked` kills once, waits at most 5 seconds, closes stdin only when `poll()` shows the child has exited, and closes the read ends. It does not report success. A process that cannot be stored and does not die within that wait remains an untracked survivor. That residual is explicit.

A `Popen` exception such as `FileNotFoundError` creates no process. The session is `SESSION_FAILED`, `children_started` is 0, and `child_alive` is false.

Windows and Linux `Popen` both return only after the OS has created the process or has failed the call. Neither platform gives this code a supported way to cancel a `CreateProcess` or `fork`/`exec` that is already blocked. A suspended-create plus job assignment would be a new launcher. That was not implemented.

## Candidate designs

| Design | Deadline | Ownership | Cleanup | Windows | Linux | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| Synchronous `Popen`, check deadline immediately before the call | In-process work before the call is covered. The call itself is not. | The returned object is registered before IPC. | Existing bounded reap. | Runs. | Runs. | Adopted. |
| Daemon thread around `Popen` | The supervisor can return at the deadline. | A process may appear after the return and be untracked. | Cannot reap a process that does not exist yet. | Unsafe. | Unsafe. | Rejected. |
| Supervised launcher process | Moves the block into another process that still has to be created. | Two processes to track, including the launcher. | Larger cleanup surface. | Possible. | Possible. | Deferred. It is a new architecture. |
| Windows Job Object, assigned after `Popen` returns | Does not bound `Popen`. | Descendants created before assignment can escape. | `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` would cover members only. | Nested jobs on this host were not proven. | Not a Linux mechanism. | Not implemented. |
| Linux `start_new_session` and `killpg` | Does not bound `Popen`. | A child that calls `setsid` escapes. A recycled pid makes `killpg` unsafe. | Not equivalent to a job object. | Not the same API. | Unsafe without a verified pid lifetime. | Not implemented. |
| Create the child suspended, assign containment, then resume | Closes the descendant race. | Requires a private `CreateProcess` path. | Strong if the job or group is correct. | Substantial unreviewed launcher. | Different calls. | Deferred to a separate stage. |

## Process ownership

The tracker owns direct children only. `children_started` is the number of `Popen` objects retained after cleanup. `child_alive` is recomputed from `poll()` after cleanup. If `poll()` raises, `child_alive` is set true. A session is complete only when the error is `NONE`, the child is not alive, the child was not terminated, and a real broker response was received. The harness does not receive one, so a clean harness stays `SESSION_INCOMPLETE`.

## Termination

`kill()` is `TerminateProcess` on Windows and `SIGKILL` on Linux. It is not `terminate()` and not `SIGTERM`. A child that handles `SIGTERM` and sleeps was still reaped, with `child_alive` false, on both tested hosts.

`PermissionError` and other `OSError` values from `kill()` are caught. `wait(timeout=5)` is tried, then one more kill and one more 5 second wait. `poll()` after those waits is the exit evidence. A fake whose `kill()` does nothing and whose `wait()` times out stays `child_alive` true, with `child_terminated` true. That pair means termination was attempted and the child survived. It is not a reap.

A child that has already exited when it is registered is tracked, reported not alive, and classified from the IPC result (`CHILD_CRASHED` when the pipe is already broken).

Stdin is not closed while `poll()` is `None`. That preserves the R.59 correction. The full-pipe regression still kills a non-reading sleeper before any supervisor-thread close, inside an 8 second outer process, and records `SESSION_DEADLINE` with `child_alive` false.

Cleanup that raises, or `poll()` that raises, does not replace an existing `SESSION_DEADLINE` with a success. `child_alive` stays true when the final `poll()` fails. Exception text is not copied into the record.

No raw IPC frame or credential is written to the record. Socket creation and connect are patched to raise in the suite. `run_real_session` still raises `REAL_OANDA_SESSION_NOT_AUTHORISED` before a prompt.

## Descendants

The diagnostic worker source contains no `Popen` and was not given descendant-spawning behaviour.

A synthetic parent that starts a grandchild was placed on `ChildTracker`. Cleanup killed the parent. The grandchild was still alive on Windows and on WSL2 Ubuntu. The test then stopped the grandchild. Cleanup returns `None` and has no field that reports the grandchild as reaped.

A process group was not used. A Windows job was not used. Those mechanisms do not provide the same guarantee, and a correct race-free version needs a suspended create plus an owned job or group. That launcher was not added.

## Resource lifecycle

| Resource | After a normal exit | While the child survives `kill()` | If the object cannot be stored |
| --- | --- | --- | --- |
| Direct child | `poll()` is not `None`. `child_alive` false. | `child_alive` true. | Kill and one 5 second wait. Survival is not called success. |
| Stdin | Closed, then detached before `communicate()` so Linux does not flush a closed stream. | Left open. The blocked daemon writer is retained. | Closed only if `poll()` shows exit. |
| Stdout and stderr | Closed. | Closed. | Closed. |
| IPC writer thread | Finishes when the write finishes. | Remains blocked with the frame until the child reads or the parent exits. | Same, if a write was started. A failed launch never starts one. |
| Grandchild | Not created by this worker. | Not tracked. | Not tracked. |

The retained stdin and writer are intentional. Closing them on the supervisor thread is the operation R.59 measured at 29.867 seconds. R.61 does not reintroduce it.

## Separate guarantee statuses

| Guarantee | Status |
| --- | --- |
| Startup deadline enforcement | Enforced only before `Popen` is called. A blocked `Popen` is not interrupted. Not a passing containment claim. |
| Direct-child cleanup | Verified for exit, `SIGTERM`-ignoring sleep, `PermissionError`, no-op `kill()`, broken IPC, and normal harness completion. A survivor stays `child_alive` true. |
| Descendant containment | Not implemented. The grandchild test shows survival on Windows and on this WSL2 host. |
| Windows runtime | Verified. 14 passed, three runs. |
| Linux runtime | Verified on Ubuntu 24.04.3 LTS, WSL2 kernel `6.6.87.2-microsoft-standard-WSL2`, Python 3.12.3. 14 passed, two runs. Not a bare-metal or second-distribution run. |

## Remaining limitations

- A blocked `Popen` can outlive the session deadline. The outer test kills the driver. The product code cannot cancel the call.
- If a process object cannot be stored and does not exit within the 5 second untracked wait, it is not on the tracker.
- Descendants of a tracked child are not killed.
- The daemon writer and its frame remain if the child survives termination.
- Emergency cleanup can add up to 21 seconds after the session deadline when every `wait(timeout=5)` times out: 1 second of reader join plus two 5 second waits in `_reap`, then two 5 second waits in cleanup. A kill that ends the child returns from `wait()` immediately.
- The early error path can still close stdin on the supervisor thread after a completed short write. That is not the full-pipe path.

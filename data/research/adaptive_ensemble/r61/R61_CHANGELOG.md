# R.61 Changelog

R.59 and R.60 were not modified. R.60 hashes still match archive `4d2c490b35fa648a09acc3af0c7f655f24703cda34c85fd259bb25e3a0e6d53d`.

R.61 is a separate copy under `data\research\adaptive_ensemble\r61\`. Loader cache names are `r61_`. Protocol identifiers stay on the R.59 contract. The copies use LF newlines. `REAL_SESSION_SOURCE_ENABLEMENT` remains false.

No Windows job object, Linux process group, or daemon-thread `Popen` wrapper was added.

## Deadline check immediately before process creation

Source file: `diagnostic_supervisor.py`. Function: `_spawn`.

Defect: the session deadline was checked at the start of `_spawn`, then capability and frame construction ran, and `Popen` followed with no second check. In-process work could pass the deadline and still create a child.

Before: a frame builder that slept past a 0.2 second deadline still reached `Popen`.

After: `_spawn` raises `SESSION_DEADLINE` when `deadline_at` has passed, before `Popen`. `children_started` stays 0. `child_terminated` stays false. No process exists.

Regression: `test_deadline_before_popen_does_not_create_a_process`.

Remaining risk: a `Popen` call that has already entered the operating system is not interrupted. `test_blocked_popen_is_not_interrupted_by_the_session_deadline` shows a 30 second stall still running 0.5 seconds after a 0.25 second deadline. The outer test kills that driver. Startup containment is not claimed.

## Keep a created process if registration raises

Source file: `diagnostic_supervisor.py`. Functions: `_spawn` and `_release_untracked`.

Defect: `Popen` could return and `ChildTracker.add` could raise before the object was stored. Cleanup would not see the child.

Before: the next line after `Popen` was `tracker.add(proc)`. An exception from `add` skipped the tracker.

After: on that exception the object is appended directly, then the exception propagates. Cleanup in `finally` still owns it. If the append also fails, `_release_untracked` kills once, waits at most 5 seconds, closes stdin only after `poll()` shows exit, and closes stdout and stderr. It returns `None` and does not report a reap. A `poll()` failure is treated as still alive, so stdin stays open.

Regression: `test_registration_failure_keeps_the_process_for_cleanup` and `test_untracked_release_does_not_close_a_live_stdin`.

Remaining risk: if the object cannot be stored and the child survives the 5 second wait, it is untracked. A blocked `Popen` that has not returned is also untracked, by the rejected-thread decision above.

## Not changed

Descendant containment was not implemented. `test_grandchild_survives_parent_termination` shows the grandchild alive after the tracked parent is killed, on Windows and on WSL2, and the test then stops the grandchild.

The synchronous full-pipe close was not restored. `test_real_pipe_deadline_still_kills_before_close` still expects `SESSION_DEADLINE` and `child_alive` false inside an 8 second outer process.

The worker was not given a way to spawn descendants. Strategy, sizing, trailing stops, risk controls, and broker execution were not edited.

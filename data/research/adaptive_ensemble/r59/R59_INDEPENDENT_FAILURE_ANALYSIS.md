# R.59 Independent Failure Analysis

**REAL_NETWORK_EXECUTION_NOT_TESTED**

Production trading remains NO-GO. This document records an investigation. It does not enable the R.59 gate, create a permit, or authorise a broker connection.

## A. Environment verification

Project root: `C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st`.

The R.59 modules are ordinary files, not an installed package. `test_r59_offline.py` loads each module by file path from its own directory (`HERE`). The supervisor starts the worker as `sys.executable -B <directory>\diagnostic_worker.py` with `cwd` set to that same directory. The worker then loads its siblings by file path. No `PYTHONPATH`, pytest plugin, or third-party package is required for this suite.

`ROOT = HERE.parents[3]` is the project root only when the test file lives at `data\research\adaptive_ensemble\r59\`. That root is used solely to locate the R.56 gate and the consumed-permit marker. The other eleven tests do not read those paths.

| Item | Observed value |
| --- | --- |
| Python | 3.13.5, `C:\Python313\python.exe` |
| pytest | 8.4.1 |
| Intended command | `python -B -m pytest -p no:cacheprovider --noconftest data\research\adaptive_ensemble\r59\test_r59_offline.py -q` |
| Working directory | the project root |
| Environment variables required by the suite | none |
| Credential source | none. `read_environment` and `read_dotenv` raise `REAL_CREDENTIAL_USE_NOT_AUTHORISED` |
| Network | parent sockets are replaced with functions that raise. The harness child replaces `HTTPSConnection` |
| R.59 gate | `live_session_gate.py` line 16 is `REAL_SESSION_SOURCE_ENABLEMENT = False` |
| R.59 permit | `data\research\adaptive_ensemble\r59\real_activation` does not exist |
| R.56 gate | `phase6_connection_enablement\live_session_gate.py` line 20 is `REAL_SESSION_SOURCE_ENABLEMENT = False` |
| R.56 permit | `one_session.consumed` is present. `one_session.permit` is absent |

`tests\conftest.py` is not on the parent path of the R.59 tests, so it is not loaded for this file. `--noconftest` remains the intended invocation. The suite does not import `forex_bot`, `requests`, or `oandapyV20`.

Twelve tests are collected from `test_r59_offline.py`. The file contains no skip mark and no exclusion of its own.

## B. Test reproduction

### Intended tree

Command, from the project root:

```text
python -B -m pytest -p no:cacheprovider --noconftest data\research\adaptive_ensemble\r59\test_r59_offline.py -q --tb=line
```

Result: **12 passed, 0 failed, 0 skipped, 0 deselected, 7.29 seconds.**

That matches the previously reported 12 passing tests. Collection did not drop a test.

### Nine-file ZIP in a directory that is not the project tree

The archive was extracted to a temporary directory that contains only the nine Python files. The same command was run against that copy.

Result: **11 passed, 1 failed, 7.19 seconds.**

The only failure was `test_source_gate_file_is_off_and_r56_evidence_is_untouched`. `HERE.parents[3]` resolved to `C:\Users\Brian`, so the test looked for `C:\Users\Brian\data\research\adaptive_ensemble\r56\phase6_connection_enablement\live_session_gate.py` and raised `FileNotFoundError`. The four worker tests named by the review passed in this layout.

This test fails closed. It does not skip, and it does not treat a missing marker as permission.

### Worker file withheld

The nine-file copy was repeated with `diagnostic_worker.py` renamed aside, and the R.56 evidence test deselected, because that is the one test which does not belong to a source-only bundle.

Result: **4 failed, 7 passed, 1 deselected, 3.41 seconds.**

That is the same count pattern as the review (7 passed, 4 failed, 1 excluded). The four failures are the four tests named below, and each one failed because the child produced no protocol payload.

## C. Failure analysis

The review did not include assertion text. The classification below is from reproducing the same four tests in this tree and in a source-only copy. With the worker file present, those four tests pass. With the worker file absent, they fail in the way the review described.

### 1. Harness metadata results

- Test: `test_harness_session_keeps_secrets_and_raw_bodies_out_of_the_log`
- Expected: `error_code == "NONE"` and `instruments[0]["marginRate"]["value"] == "0.03330000"`, with the account id, token, and raw-body marker absent from the log.
- Actual in the intended tree: passed.
- Actual when the worker file is absent: `IndexError: list index out of range` at the `instruments[0]` assertion (test line 262). The record has no instruments because the child result was not a protocol payload.
- Root cause of the reproduced failure: Python starts, the script path cannot be opened, stdout is empty, and the supervisor records `CHILD_CRASHED`. The test then indexes an empty instrument list.
- Source: `diagnostic_supervisor.py` treats an empty child result as `CHILD_CRASHED` after `_spawn` returns no payload. `diagnostic_worker.py` `main` is what must emit the metadata line.
- Classification: **environment defect** for the reported failure. It is not a metadata-extraction defect in the current source. The same test passes when `diagnostic_worker.py` is beside the supervisor.
- Correction: run the suite from a directory that contains all nine Python files, using the command in section B. Do not change the assertion.

### 2. Worker timeout handling

- Test: `test_timeout_and_spawn_fault_reap_the_child`
- Expected: a `stall="hang"` child is killed on the 2 second request cap while the 15 second session clock still has time, with `error_code == "CHILD_TERMINATED"` and `child_alive is False`.
- Actual in the intended tree: passed.
- Actual when the worker file is absent: `assert 'CHILD_CRASHED' == 'CHILD_TERMINATED'` (test line 285).
- Root cause: the child exits immediately with empty stdout. The request-cap path that returns `CHILD_TERMINATED` is never reached. An empty result is `CHILD_CRASHED`, which is the fail-closed classification for an unexpected exit.
- Source: `diagnostic_supervisor.py` ready-wait and `communicate` timeout branches. `diagnostic_worker.py` lines 89–90 sleep only after `CAP_OK` when `stall` is `hang`.
- Classification: **environment defect** for the reported failure. The current timeout branch is exercised by the passing run.
- Correction: same as item 1. No test change.

### 3. Overall session deadline handling

- Test: `test_overall_deadline_bounds_every_wait`
- Expected: `stall="delay-then-hang"`, `request_deadline=5`, `session_deadline=1.25`, wall time under 3 seconds, `error_code == "SESSION_DEADLINE"`, `session_status == "SESSION_INCOMPLETE"`, child not alive.
- Actual in the intended tree: passed inside the 7.29 second full run.
- Actual when the worker file is absent: `assert 'CHILD_CRASHED' == 'SESSION_DEADLINE'` (test line 380).
- Root cause of that reproduced failure: the child never reaches the 0.35 second pre-ready delay, so the session deadline is not what stops the wait. Empty stdout becomes `CHILD_CRASHED`.
- Source: one `deadline_at` is taken in `_execute` and passed into `_spawn`. `diagnostic_worker.py` lines 75–76 and 89–90 implement `delay-then-hang`.
- Classification: **environment defect** for the reported failure. A separate, proven source defect in `_ipc_send` is recorded in section D. That defect did not cause this test to fail here, because this test's frame is small and the child reads stdin.
- Correction: keep this test. Add a real-pipe regression for the section D defect. Do not loosen the 3 second bound to hide a missing worker.

### 4. Malformed worker responses

- Test: `test_malformed_exit_and_cleanup_failures_stay_incomplete`
- Expected: `stall="malformed"` yields `MALFORMED_CHILD_RESULT`; `stall="exit"` yields `CHILD_CRASHED`; `fault_at="cleanup"` yields `CHILD_CLEANUP_FAILED`; every case is `SESSION_INCOMPLETE` and the child is not alive.
- Actual in the intended tree: passed.
- Actual when the worker file is absent: `assert 'CHILD_CRASHED' == 'MALFORMED_CHILD_RESULT'` (test line 398). The malformed fixture never runs.
- Root cause: there is no stdout line `{not-json` to parse. `json.loads` is not reached. Empty output is `CHILD_CRASHED`.
- Source: `diagnostic_worker.py` lines 83–86 write `{not-json` and call `os._exit(0)`. `diagnostic_supervisor.py` maps `JSONDecodeError` to `MALFORMED_CHILD_RESULT`.
- Classification: **environment defect** for the reported failure.
- Correction: same as item 1.

The seventh passing tests in the withheld-worker run are the tests that do not need a live protocol result: entry refusal, permit handling, transport checks, metadata extraction, the persistence patch, the in-memory blocked-write double, and the source scan. The persistence test still passes because it replaces `_persist_record` with a function that raises, so the worker outcome is overwritten. The in-memory IPC test passes because it replaces `Popen`.

## D. IPC and deadline audit

One monotonic `deadline_at` is computed at the start of `_execute` and is not reassigned. Readiness, the frame send, the capability acknowledgement, the early worker-response wait, and `communicate` all use the time remaining against that value. A request cap that fires while session time remains still returns `CHILD_TERMINATED`. That path passed `test_timeout_and_spawn_fault_reap_the_child`.

`_ipc_send` (`diagnostic_supervisor.py` lines 157–187) writes and flushes on a daemon thread and joins that thread for the remaining session time. A `BrokenPipeError` or any other exception inside the thread becomes the status `broken`. The exception text is not stored. The caller then reaps the child and records `CHILD_CRASHED` with `SESSION_INCOMPLETE`. The offline fake-stream tests cover that classification and check that a marker placed in the exception is absent from the record.

Partial writes are inside `BufferedWriter.write`. The caller does not see a short count. A write that blocks remains inside the daemon thread until the join expires. That part of the design holds.

**Proven defect:** after the join expires, lines 181–185 call `stream.close()` on the supervisor thread. On this Windows host, `stdin.close()` flushes, and that flush blocks while the pipe is full and the child is still alive. A diagnostic process wrote 256 KiB to a child that slept for 20–30 seconds and did not read stdin.

- The writer thread was blocked.
- `close()` on the caller thread did not return until the child exited by itself. Elapsed time was **29.867 seconds**. The child exit code was 0. The supervisor had not reached `kill`.
- The same `close()`, started on another thread, stayed blocked. `proc.kill()` then let both threads finish. Time from `kill` to both threads leaving the pipe was **0.001 seconds**. The writer received `BrokenPipeError`.
- `close()` after `kill` returned in **0.001 seconds**.

`_reap` already kills before it closes stdin (lines 201–208) and bounds `wait` at 5 seconds, then 5 seconds again. `_ipc_send` never reaches `_reap` while `close()` is blocked, so that safe order is not used on the deadline path. The daemon thread does not remain blocked after `close()` finally returns, but the supervisor thread itself has already overrun the deadline.

The current blocked-write tests do not catch this. Their stand-in stream implements `close()` as setting an event and returning. That proves the supervisor stops waiting on the stand-in. It does not prove that closing a real Windows pipe is bounded.

A timeout path does not open a socket. The harness child replaces `HTTPSConnection` before it parses the frame. A real child calls `assert_real_session` before parsing, and the source gate is false. The blocked-pipe diagnostic used a local `sleep` process only.

Atomic persistence is unchanged. `_persist_record` (line 235) still writes `session_id.json.tmp`, calls `fsync`, and `os.replace`s onto `session_id.json`. A failed write, replace, or directory creation leaves no successful file and returns `RECORD_PERSISTENCE_FAILED`. Those tests passed in the intended run.

## E. Security invariant review

| Requirement | Result | Evidence |
| --- | --- | --- |
| Production trading disabled | Pass | R.59 gate line 16 is false. This run did not start `main.py` or import the trading package. |
| No order submission during testing | Pass | Transport tests reject an `/orders` path. `RestrictedLiveTransport` has no `create_order`. The suite passed with sockets blocked. |
| No real-network execution | Pass | No connection to `api-fxtrade.oanda.com` was made. Harness transport raises `HARNESS_NETWORK_FORBIDDEN`. |
| Credentials not copied into diagnostic records | Pass | The harness log test passed. It rejects the synthetic account id, the synthetic token, and `Bearer`. |
| IPC frames and pipe errors do not expose secrets | Pass for the recorded result | `_ipc_send` stores `ok`, `deadline`, or `broken` only. The fake broken-pipe test checks that its exception marker is absent. The blocked real-pipe probe did not put the payload into an exception that the supervisor records. |
| R.56 permit cannot be reused | Pass | `one_session.consumed` is present and `one_session.permit` is absent. The R.59 tests do not consume it. |
| Failure paths reject | Pass | Empty child output, a broken pipe, a malformed line, a missed deadline, and a persistence error all end as `SESSION_INCOMPLETE`. |
| Missing evidence is not approval | Pass | A ZIP-only directory fails `test_source_gate_file_is_off_and_r56_evidence_is_untouched` with `FileNotFoundError`. The R.59 gate stays false and no permit directory is created. |

## F. Recommended corrective actions

1. **Bound the real pipe close.** In `_ipc_send`, do not call `stream.close()` on the supervisor thread after a timed-out write. Return `deadline` and let the existing `_reap` kill the child first. The probe showed that `kill` unblocks the writer and that `close()` after `kill` returns in about a millisecond. Add one offline test that fills a real `stdin` pipe, uses a session deadline under one second, and asserts the call returns `SESSION_DEADLINE` well before the child would have exited on its own. Do not implement that change in this investigation.
2. **Re-run the review on the nine co-located files.** The reported 7/4/1 split was reproduced by withholding `diagnostic_worker.py` and deselecting the R.56 test. It was not reproduced when the nine files were together. The review command should be the one in section B, from the project root. Capture the assertion text if any test still fails.
3. **Keep the R.56 test in the project-tree run.** A source-only directory cannot satisfy it. Excluding it hides a missing consumed marker. It must not be replaced with a dummy permit or a dummy gate file.
4. **Do not change the four assertions to accept `CHILD_CRASHED`.** That status means the worker protocol did not run.

No production trading file, R.56 file, gate constant, or permit was changed while gathering this evidence.

## G. Final gate recommendation

**`R59_OFFLINE_GATE_FAIL`**

The intended tree does collect and pass all 12 tests in 7.29 seconds, and the four review failures were reproduced only when the worker produced no protocol stdout. Those four results are not a defect in the current metadata, timeout, deadline, or malformed-response logic.

The gate still fails because `_ipc_send` can block the supervisor inside `stream.close()` for the life of the child. On this host that was 29.867 seconds, far past any R.59 session deadline of 15 seconds. The existing blocked-write tests use a fake stream and do not see that stall. Until the close is ordered after `kill` and a real-pipe test locks that order in, the offline deadline claim is not proven.

This recommendation is not permission to enable the R.59 gate, call OANDA, or run production trading.

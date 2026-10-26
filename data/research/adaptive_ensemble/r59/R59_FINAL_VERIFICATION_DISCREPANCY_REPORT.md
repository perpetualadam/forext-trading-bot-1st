# R.59 Final Verification Discrepancy

**REAL_NETWORK_EXECUTION_NOT_TESTED**

Production trading remains NO-GO. This is a diagnostic record. No production source, test assertion, gate, or permit was changed.

## A. Environment comparison

| | Original project tree | Isolated archive extract |
| --- | --- | --- |
| Operating system | Windows 11, 10.0.26300 | Same host. Linux was not available |
| Python | 3.13.5 | 3.13.5 |
| Executable | `C:\Python313\python.exe` | Same executable |
| pytest | 8.4.1 | 8.4.1 |
| Working directory for pytest | project root | the extracted `...\r59` directory |
| Module directory | `data\research\adaptive_ensemble\r59` | `...\Temp\r59_archive_extract\data\research\adaptive_ensemble\r59` |
| Archive SHA-256 | `2652508e3011d86c59c97e1ce65aebe9b29b6392e5264defe78957369f441d63` | Same file, extracted |
| Python files present | the nine R.59 modules | the same nine names |
| `diagnostic_worker.py` | present and readable | present, readable, 6517 bytes |
| Worker path used by the supervisor | absolute path beside `diagnostic_supervisor.py` | absolute path, file existed |
| R.56 gate and consumed marker | present in the project tree | not inside the archive |

The supervisor sets `WORKER` from its own file location, then starts `[sys.executable, "-B", absolute-worker-path, "--authenticated-worker", "--harness-transport"]` with `cwd` equal to that directory. The child environment keeps `PATH` and the Windows system variables. It does not keep `HOME`. No `.env` file is read.

The suite has no skip mark. Pytest reports "deselected" only when a `-k` or `-m` filter excludes a test. The only test that needs files outside the nine is `test_source_gate_file_is_off_and_r56_evidence_is_untouched`.

## B. Test results

Project tree:

```text
python -B -m pytest -p no:cacheprovider --noconftest data\research\adaptive_ensemble\r59\test_r59_offline.py -q --tb=line
```

**13 passed, 0 failed, 7.90 seconds.**

Isolated extract of the verified archive, same command, cwd set to the extracted module directory:

**1 failed, 12 passed, 7.72 seconds.**

The only failure was `FileNotFoundError` for `...\r59_archive_extract\data\research\adaptive_ensemble\r56\phase6_connection_enablement\live_session_gate.py`. The four worker tests passed.

Same extract with that one test deselected:

**12 passed, 1 deselected, 7.61 seconds.**

A second copy of that extract, with `diagnostic_worker.py` renamed aside and the R.56 test deselected:

**4 failed, 8 passed, 1 deselected, 3.94 seconds.**

That is the independent count. The four failures and their assertions were:

| Test | Assertion |
| --- | --- |
| `test_harness_session_keeps_secrets_and_raw_bodies_out_of_the_log` | `IndexError` at `instruments[0]` (line 262) |
| `test_timeout_and_spawn_fault_reap_the_child` | `'CHILD_CRASHED' == 'CHILD_TERMINATED'` (line 285) |
| `test_overall_deadline_bounds_every_wait` | `'CHILD_CRASHED' == 'SESSION_DEADLINE'` (line 380) |
| `test_malformed_exit_and_cleanup_failures_stay_incomplete` | `'CHILD_CRASHED' == 'MALFORMED_CHILD_RESULT'` (line 398) |

The eight passes are the tests that do not need a worker protocol result: entry refusal, permit handling, transport, metadata extraction, the persistence patch, the fake-pipe IPC test, the real-pipe regression, and the source scan. The real-pipe regression replaces `Popen` with a local sleep child, so it still passes when `diagnostic_worker.py` cannot be opened. That is why this archive's count is 8 passed rather than the earlier 7.

## C. Worker lifecycle

When the nine files share a directory, a harness session does the following:

1. The supervisor builds one IPC frame in memory and starts the absolute worker path.
2. The probe recorded `script_name` `diagnostic_worker.py`, `script_is_absolute` true, and `script_exists` true.
3. The worker loads its siblings from its own directory. Stderr length was 0.
4. The child accepted the frame. With an intentionally empty instrument list it returned a protocol body of 420 stdout bytes and exit code 1.
5. The supervisor classified that body as `INSTRUMENT_SET_REJECTED`, not as an empty result. The account id and token were absent from the record.
6. The normal six-instrument harness test in the same directory returned a completed metadata record. Those four tests passed.

The empty-protocol branch is `diagnostic_supervisor.py` around the `communicate` result: if stdout is empty, `_spawn` returns no payload, and `_execute` records `CHILD_CRASHED`. A direct start of a missing worker path exited **2**, wrote **0** stdout bytes, and the stderr class was **script_not_opened** (163 bytes, not copied here). The supervisor does not store that stderr in the diagnostic record, so the tests only show `CHILD_CRASHED` or an empty instrument list.

No capability acknowledgement is required for that classification. The child has already exited.

## D. Four-failure investigation

### 1. Harness metadata extraction

- Expected: `error_code == "NONE"` and a preserved `marginRate` string.
- Project tree: passed.
- Isolated archive with the worker present: passed.
- Isolated copy with the worker path unopenable: `IndexError` on `instruments[0]`.
- Subprocess: exit 2, stdout empty, stderr class `script_not_opened`.
- Classification: **environmental**. The current source extracts metadata when the worker file beside the supervisor can be opened. The failing assertion is the empty-result symptom, not a wrong field mapping.

### 2. Worker timeout and termination

- Expected: `CHILD_TERMINATED` for `stall="hang"`, child not alive.
- Project tree: passed.
- Worker present in the archive extract: passed.
- Worker path unopenable: `CHILD_CRASHED`.
- The hang fixture never runs, so the request cap is not what stops the child. The process exits immediately.
- Classification: **environmental**.

### 3. Overall session deadline

- Expected: `SESSION_DEADLINE` and `SESSION_INCOMPLETE` for `stall="delay-then-hang"` inside the 1.25 second deadline.
- Project tree: passed.
- Worker present: passed.
- Worker path unopenable: `CHILD_CRASHED`.
- The 0.35 second pre-ready delay never starts.
- Classification: **environmental**. This is not the pipe-close defect. That path is covered by the real-pipe regression, which does not launch `diagnostic_worker.py`.

### 4. Malformed worker response

- Expected: `MALFORMED_CHILD_RESULT` for `stall="malformed"`.
- Project tree: passed.
- Worker present: passed.
- Worker path unopenable: `CHILD_CRASHED`.
- The `{not-json` line is never written, so the JSON decoder is not the code that fails.
- Classification: **environmental**.

No assertion was changed. A source defect would have failed these four tests in the project tree and in the faithful archive extract. Both of those runs passed them.

## E. Real-pipe regression

`test_real_pipe_deadline_kills_before_close` was run five times with:

```text
python -B -m pytest -p no:cacheprovider --noconftest data\research\adaptive_ensemble\r59\test_r59_offline.py -q --tb=line -k test_real_pipe_deadline_kills_before_close
```

| Run | Result | Time |
| --- | --- | --- |
| 1 | 1 passed, 12 deselected | 0.73 s |
| 2 | 1 passed, 12 deselected | 0.91 s |
| 3 | 1 passed, 12 deselected | 0.63 s |
| 4 | 1 passed, 12 deselected | 0.64 s |
| 5 | 1 passed, 12 deselected | 0.64 s |

The test uses a real OS pipe, a child that does not read stdin, and a 0.4 second session deadline inside an 8 second outer process. A pass means the supervisor returned `SESSION_DEADLINE` and `SESSION_INCOMPLETE`, the child was not alive, and the record did not contain the synthetic account id, token, bearer text, or the pipe padding. The timeout return does not send the capability acknowledgement. The IPC close-before-kill behaviour was not changed.

## F. Security verification

| Control | State after this diagnostic |
| --- | --- |
| R.59 source gate | `REAL_SESSION_SOURCE_ENABLEMENT = False` |
| R.56 source gate | `REAL_SESSION_SOURCE_ENABLEMENT = False` |
| R.56 consumed marker | `one_session.consumed` is present |
| R.56 permit | `one_session.permit` is absent |
| R.59 permit directory | absent |
| Network | no OANDA connection. The isolated probe and the regression used local processes only |
| Orders and trading code | not modified and not started |
| Credentials and `.env` | not read |

## G. Outstanding limitations

Linux, and any other non-Windows host, was not available. Cross-platform execution of this suite is **unverified**.

The child environment omits `HOME`, `LANG`, and `LD_LIBRARY_PATH`. On this Windows host the worker still started. Whether a Linux interpreter wrapper would fail under that environment was not tested. The real-pipe regression also uses that environment and passed, which shows that `python -c` can start here with the stripped environment.

This diagnostic did not inspect the independent reviewer's process list or their extracted directory. What was shown is that their published counts and the four assertion failures are the result of Python being unable to open `diagnostic_worker.py`. They are not the result of the nine hashed files when those files are extracted together and the worker path exists.

## H. Final recommendation

**`R59_VERIFICATION_DISCREPANCY_RESOLVED`**

**`R59_OFFLINE_GATE_PASS`**

The project-tree suite passed 13 tests. The same archive, extracted with its relative paths, passed the four worker tests and failed only the R.56 evidence test, which the archive is not supposed to contain. Deselecting that test left 12 passes. The independent 8/4/1 result was reproduced by leaving the worker path unopenable. The real-pipe regression passed five times.

This does not enable the R.59 gate, an OANDA connection, or production trading.

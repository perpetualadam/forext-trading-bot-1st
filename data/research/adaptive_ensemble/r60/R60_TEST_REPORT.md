# R.60 Test Report

## Commands

From the project root:

```
python -B -m pytest -p no:cacheprovider --noconftest data\research\adaptive_ensemble\r59\test_r59_offline.py -q --tb=line
python -B -m pytest -p no:cacheprovider --noconftest data\research\adaptive_ensemble\r60\test_r60_offline.py -q --tb=line
python -B -m pytest -p no:cacheprovider --noconftest data\research\adaptive_ensemble\r60\test_r60_offline.py -q --tb=line -k test_real_pipe_deadline_kills_before_close
```

Linux, from the same tree mounted in WSL2. System Python had no pytest, so the runner was a virtual environment created with `python3 -m venv "$HOME/r60pytest"` and `pip install pytest`. The tests themselves ran under `/usr/bin/python3` via that environment:

```
python -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r60/test_r60_offline.py -q --tb=line
python -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r59/test_r59_offline.py -q --tb=line
```

## Environments

| Host | Result used for |
| --- | --- |
| Windows 11 10.0.26300, Python 3.13.5, pytest 8.4.1, `C:\Python313\python.exe` | R.59 baseline and R.60 Windows runs |
| Ubuntu 24.04.3 LTS, WSL2 kernel `6.6.87.2-microsoft-standard-WSL2`, Python 3.12.3, pytest 9.1.1 | R.60 Linux runs and the R.59 Linux comparison |

No test opened a socket. The parent patches `socket.create_connection` and `socket.socket.connect`. Credentials in the tests are the synthetic account `001-002-0000001-003` and the synthetic token `SYNTHETIC-NOT-REAL-R59-TOKEN`.

## Counts

R.59 Windows baseline, before R.60 edits: 13 collected, 13 passed, 0 failed, 0 skipped, 0 deselected, 7.76 seconds.

R.59 Windows after R.60: 13 collected, 13 passed, 0 failed, 0 skipped, 0 deselected, 7.66 seconds.

R.60 Windows, final tree: 19 collected, 19 passed, 0 failed, 0 skipped, 0 deselected. Three runs: 8.04 seconds, 8.11 seconds, 7.99 seconds.

R.60 Linux, final tree: 19 collected, 19 passed, 0 failed, 0 skipped, 0 deselected. Three runs: 8.95 seconds, 9.20 seconds, 9.01 seconds.

R.59 Linux comparison, source unchanged: 13 collected, 9 passed, 4 failed, 0 skipped, 0 deselected, 6.01 seconds. See Linux status below.

The pipe filter collects 19 and deselects 18.

One R.60 test reads the R.56 gate, the consumed marker, and the absent permit outside this directory. On this project tree it passed. An extract that does not contain those R.56 files fails that test closed. The other 18 tests use only the nine archive members.

## Fault injection

| Test | Observed classification | Resource result |
| --- | --- | --- |
| `PermissionError` from `kill()` | `SESSION_DEADLINE`, `SESSION_INCOMPLETE`, `child_alive` true | Stdin left open. Stdout and stderr closed. `wait` called with timeout 5. Elapsed under 2 seconds. |
| `OSError` from `kill()` | `SESSION_DEADLINE`, `child_alive` true | Stdin left open. Stdout closed. |
| Child exits as `kill()` is attempted | `SESSION_DEADLINE`, `child_alive` false | Stdin closed only after the exit is visible. |
| `wait()` times out and `kill()` does not change `poll()` | `SESSION_DEADLINE`, `child_terminated` true, `child_alive` true | Not reported reaped. Timeout argument is 5. |
| Writer blocked on the IPC stream | `SESSION_DEADLINE` inside 2 seconds | Supervisor returns while the daemon writer is blocked, then the test releases it. |
| Broken pipe during the write | `CHILD_CRASHED`, `child_alive` false | Exception text is absent from the record. |
| Worker file missing | `CHILD_CRASHED`, `children_started` 1, `child_alive` false | Real Python process exits. No secret in the record. |
| Worker stdout empty | `CHILD_CRASHED`, `child_alive` false | Real Python process exits. |
| Malformed protocol line | `MALFORMED_CHILD_RESULT`, instruments empty | Real worker. Passed on Windows and Linux. |
| `fault_at=cleanup` after a clean harness | `CHILD_CLEANUP_FAILED`, `child_alive` false | Record persisted. Status stays incomplete. |
| `poll()` raises during cleanup | `SESSION_DEADLINE` retained, `child_alive` true | Exception text absent. |
| Deadline exhausted before `Popen` | `SESSION_DEADLINE`, `children_started` 0, `child_terminated` false | `Popen` is not called. |
| Deadline during `delay-then-hang` startup | `SESSION_DEADLINE`, `child_alive` false, `children_started` 1 | Elapsed under 3 seconds. |
| Reader still blocked after the ready budget | `SESSION_DEADLINE`, `child_alive` false | Elapsed from 0.9 to 3 seconds, covering the 1 second reader join. |
| Three real sessions and five deadline sessions | Each real session `NONE`, `child_alive` false, six instruments | Thread count did not grow by more than one. |
| Parent with a grandchild | Tracked parent exits. Grandchild was still alive. | The test stopped the grandchild. Cleanup's return value is `None`. |
| Closed stdin passed to `communicate()` | `MALFORMED_CHILD_RESULT` | The fake raises `ValueError` if stdin is still attached. |

Every failure record above was `SESSION_INCOMPLETE`, with `executable_order` `NOT_PRODUCED`, `live_network_access` `REAL_NETWORK_NOT_COMPLETED`, `network_attempted` false, and `broker_response_received` false. Saved JSON omitted the synthetic account, the synthetic token, `Bearer`, and the raw-body marker.

`run_real_session` raised `REAL_OANDA_SESSION_NOT_AUTHORISED` and did not call the prompt.

## Real-pipe regression

`test_real_pipe_deadline_kills_before_close` runs a second Python process with an 8 second timeout. That process pads a real IPC frame with 256 KiB and starts a child that sleeps instead of reading. The session deadline is 0.4 seconds.

Windows, five runs on the final tree: 1 passed and 18 deselected each time. Pytest times 0.64, 0.64, 0.65, 0.64, and 0.65 seconds. Each run asserts `SESSION_DEADLINE`, `SESSION_INCOMPLETE`, `child_alive` false, driver elapsed under 3 seconds, outer elapsed under 4 seconds, and no account, token, `Bearer`, or padding in the record.

The same test passed on each Linux suite run.

## Repeated-run stability

Windows full suite, final tree: 19 passed in 8.04, 8.11, and 7.99 seconds.

Linux full suite, final tree: 19 passed in 8.95, 9.20, and 9.01 seconds.

No order was submitted and no gate file changed.

## Linux verification status

Linux runtime verification was performed. It is not inferred from Windows.

Host: Ubuntu 24.04.3 LTS on WSL2, kernel `6.6.87.2-microsoft-standard-WSL2`, CPython 3.12.3, pytest 9.1.1.

R.60: passed, 19 tests, three runs.

R.59 on that same interpreter: 4 failed, 9 passed. The worker-completion tests returned `SESSION_FAILED` because `Popen.communicate()` flushed an already closed stdin (`ValueError: flush of closed file`). The R.60 copy detaches that handle. The R.59 files were not modified, and the Windows R.59 suite still passes.

This is one WSL2 Ubuntu environment. It is not a bare-metal run and not a second distribution.

## Archive

`data\research\adaptive_ensemble\r60\R60_SOURCE_REVIEW.zip`

- Size: 27472 bytes
- SHA-256: `4d2c490b35fa648a09acc3af0c7f655f24703cda34c85fd259bb25e3a0e6d53d`

Members, uncompressed SHA-256:

| Bytes | SHA-256 | Member |
| --- | --- | --- |
| 8515 | `a6f4e0df6fb52c559a0584478c3201a28e983a4da6041c1dd16573eba7a15099` | `data/research/adaptive_ensemble/r60/credential_ipc.py` |
| 23929 | `7530b2f5bf47bc647808be44eaaad58fa83e91b34ed11349bc4e6b3c42194459` | `data/research/adaptive_ensemble/r60/diagnostic_supervisor.py` |
| 6517 | `a5e6eff488c4dbd6ae24bdaebbe69a341fd60f7fcf456f1c9259758c75a1d974` | `data/research/adaptive_ensemble/r60/diagnostic_worker.py` |
| 10533 | `2378037d15e4346edf3c421ef24b791e5993f00ade7f9ea9a1b3c2f837e74ab2` | `data/research/adaptive_ensemble/r60/live_session_gate.py` |
| 6337 | `259b9ec4dec03eda81cb9c9713d954ae694695cbfc04c4f8385cef73b50468ab` | `data/research/adaptive_ensemble/r60/metadata_extract.py` |
| 3842 | `0b68ae763aaba886b668d59fd2286b956b97c28facc3feab8658df0884d9b970` | `data/research/adaptive_ensemble/r60/one_session_activation.py` |
| 1755 | `7fa69a1dfc9e239479a287dc0a9a8f06bcb529e85650dad2474744a82976bbf5` | `data/research/adaptive_ensemble/r60/real_session_entry.py` |
| 9461 | `a0ef652dcb9b07ac7db180128ef53f141b4854681d6bb51fbaf242508452d8e7` | `data/research/adaptive_ensemble/r60/restricted_live_transport.py` |
| 27810 | `120aeb3d26358c1c72d0d69dd2e48fd6fcda50f25e570a3f9644153a0e93e254` | `data/research/adaptive_ensemble/r60/test_r60_offline.py` |

The archive contains those nine files only. It contains no credentials, `.env` file, permit, or diagnostic log. `live_session_gate.py` and `metadata_extract.py` are byte-identical to R.59. Protocol identifiers remain the R.59 contract. Loader cache names use the `r60_` prefix.

`test_r56_evidence_dependency_fails_closed_when_absent` is the test that needs the external R.56 gate and consumed marker. It fails closed when they are absent.

# R.61 Test Report

## Commands

From the project root:

```
python -B -m pytest -p no:cacheprovider --noconftest data\research\adaptive_ensemble\r60\test_r60_offline.py -q --tb=line
python -B -m pytest -p no:cacheprovider --noconftest data\research\adaptive_ensemble\r61\test_r61_offline.py -q --tb=line
```

Linux, WSL2, same tree. System Python has no pytest. The runner was `python3 -m venv "$HOME/r60pytest"` and `pip install pytest`. The suite ran under that environment's Python 3.12.3:

```
python -B -m pytest -p no:cacheprovider --noconftest data/research/adaptive_ensemble/r61/test_r61_offline.py -q --tb=line
```

## Environments

| Host | Role |
| --- | --- |
| Windows 11 10.0.26300, Python 3.13.5, pytest 8.4.1, `C:\Python313\python.exe` | Baseline and R.61 Windows runs |
| Ubuntu 24.04.3 LTS, WSL2 kernel `6.6.87.2-microsoft-standard-WSL2`, Python 3.12.3, pytest 9.1.1 | R.61 Linux runs |

No test opened a socket. Credentials are the synthetic account `001-002-0000001-003` and the synthetic token `SYNTHETIC-NOT-REAL-R59-TOKEN`.

## Counts

R.60 baseline before R.61 edits: 19 collected, 19 passed, 0 failed, 0 skipped, 0 deselected, 8.06 seconds.

R.60 after R.61, source unchanged: 19 passed, 8.01 seconds.

R.61 Windows, final tree: 14 collected, 14 passed, 0 failed, 0 skipped, 0 deselected. Three runs: 3.85 seconds, 4.25 seconds, 3.94 seconds.

R.61 Linux, final tree: 14 collected, 14 passed, 0 failed, 0 skipped, 0 deselected. Two runs: 5.34 seconds and 5.29 seconds.

One test reads the R.56 gate and consumed marker outside the archive. It passes in this project tree and fails closed when those files are absent. The other tests use the nine archive members.

## Fault injection

| Test | Classification and ownership | Timing and resources |
| --- | --- | --- |
| Deadline expires while the frame is built | `SESSION_DEADLINE`, `children_started` 0, `child_alive` false, `child_terminated` false. `Popen` was not called. | Under 2 seconds. No process. |
| `Popen` sleeps for 30 seconds inside an outer driver | The driver was still alive 0.5 seconds after the 0.25 second deadline. The outer test killed it. No child was created. Startup is not claimed to be bounded. | Outer sequence under 8 seconds. Status file does not contain the token. |
| `Popen` raises `FileNotFoundError` | `SESSION_FAILED`, `children_started` 0, `child_alive` false. Launch text is absent from the record. | Under 2 seconds. |
| Process already exited at registration | `CHILD_CRASHED`, `children_started` 1, `child_alive` false. Read handles closed. | Under 2 seconds. |
| `ChildTracker.add` raises | `SESSION_FAILED`. The process was appended for cleanup, then killed. `child_alive` false. Register text is absent. | Under 2 seconds. |
| Object cannot be stored and `kill()` does not change `poll()` | `_release_untracked` returns `None`. `poll()` stays `None`. Stdin stays open. Stdout and stderr close. Wait timeout argument is 5. | Immediate fake wait. |
| `kill()` does nothing and `wait()` times out | `SESSION_DEADLINE`, `child_terminated` true, `child_alive` true. Stdin stays open. Stdout closes. | Under 2 seconds. |
| `PermissionError` from `kill()` | `SESSION_DEADLINE`, `child_alive` true. Stdin stays open. | Under 2 seconds. |
| Child handles `SIGTERM` and sleeps | `SESSION_DEADLINE`, `child_alive` false, `children_started` 1. `kill()` still reaped it. | Under 3 seconds. |
| Blocked IPC writer on that survivor path | The writer is inside the blocked write when the session returns `SESSION_DEADLINE`. The test then releases the writer. The record has no token. | Join is the remaining session time. |
| Synthetic parent with a grandchild | Tracked parent exits. Grandchild was still alive. Cleanup duration under 3 seconds. The test then stopped the grandchild. | No leftover process asserted. |
| `poll()` raises during cleanup | `SESSION_DEADLINE` kept, `child_alive` true. Exception text absent. | Under 2 seconds. |
| Three real harness sessions | Each is `NONE`, `SESSION_INCOMPLETE`, `child_alive` false, six instruments, handles closed or stdin detached after close. | Each under 3 seconds. Thread count grew by at most one. |
| Broken IPC write at startup | `CHILD_CRASHED`, `child_alive` false, `children_started` 1. Exception text absent. | Under 2 seconds. |
| Real 256 KiB pipe, sleeper child, 0.4 second deadline, 8 second outer process | `SESSION_DEADLINE`, `SESSION_INCOMPLETE`, `child_alive` false, driver under 3 seconds, outer under 4 seconds. No account, token, `Bearer`, or padding in the record. | Included in every suite run. |

`run_real_session` raised `REAL_OANDA_SESSION_NOT_AUTHORISED` and did not prompt.

## Windows verification

Verified on this host. Three full R.61 runs passed. The R.60 suite passed before and after. The blocked-launch driver was killed by the test. The grandchild was stopped by the test. The real-pipe regression passed inside the suite.

## Linux verification

Verified by executing the suite on Ubuntu 24.04.3 LTS under WSL2. Two runs passed, 14 tests each, 5.34 and 5.29 seconds. This includes the blocked launch, the grandchild, the `SIGTERM` sleeper, the real pipe, and the harness. It is this WSL2 kernel, not a bare-metal machine and not a second distribution.

## Regression

R.60 source hashes and the 27472-byte archive hash were unchanged. R.60 tests: 19 passed in 8.01 seconds. R.56 consumed-marker hash was unchanged. No permit was created. R.61 `REAL_SESSION_SOURCE_ENABLEMENT` remains false.

## Resource-leak findings

Normal exit closes stdout and stderr. Stdin is closed and then detached so `communicate()` does not flush it. A surviving child keeps stdin and the daemon writer, and loses the read handles. An untracked fallback uses one bounded wait and does not close a live stdin. The grandchild is not owned by the tracker; the test process stops it. No suite run was left with that grandchild alive.

## Archive

`data\research\adaptive_ensemble\r61\R61_SOURCE_REVIEW.zip`

- Size: 27255 bytes
- SHA-256: `43b0acc351fb6292535ef4f86063fe4e95b6a66c9c5a8baf715f2ba93f62ab86`

| Bytes | SHA-256 | Member |
| --- | --- | --- |
| 8287 | `b4630c5b74dd0d9f73bce1f707f3b2391bffd0fe746d5b74447e728a4ced4d1b` | `data/research/adaptive_ensemble/r61/credential_ipc.py` |
| 24541 | `6ef632294778961142f261789814cd1eccfee82a1661b06b8f7b3b53c6c3fc2f` | `data/research/adaptive_ensemble/r61/diagnostic_supervisor.py` |
| 6343 | `0f70dcf2a9d6a1d7cd12f285bb6396c4aa0163148dc4943bc419d6743ab1020e` | `data/research/adaptive_ensemble/r61/diagnostic_worker.py` |
| 10271 | `2f89959f8cae0e45589b16d159f038af370aa9cec592455784046ef57230c4c0` | `data/research/adaptive_ensemble/r61/live_session_gate.py` |
| 6183 | `06561e7e8fd5fb5278929f2edfad0b18ce8c7ec5d7f4a4f13bb2c1b647bbafd3` | `data/research/adaptive_ensemble/r61/metadata_extract.py` |
| 3727 | `b64d2bbf38f65094dad93dce252a4e9a7cab5b3232f503d0112a3de3307d0447` | `data/research/adaptive_ensemble/r61/one_session_activation.py` |
| 1695 | `45e02d428aab72241350fc32c4809826e3764286d08a775607dd30a9d916a752` | `data/research/adaptive_ensemble/r61/real_session_entry.py` |
| 9236 | `b56d94edaf8d4d7ed2ae366efc6587aab9c49d7841aeef9bc5fdc7429f6d6f10` | `data/research/adaptive_ensemble/r61/restricted_live_transport.py` |
| 25148 | `e2a4196b5a0b475eeca91c035bde46dd23f6419078d9d71d2c03a973f541b613` | `data/research/adaptive_ensemble/r61/test_r61_offline.py` |

Nine files. No credentials, `.env`, permit, or diagnostic log. The R.56 test fails closed without the external R.56 files.

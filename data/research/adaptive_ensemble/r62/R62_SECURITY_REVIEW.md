# R.62 security review

The proof of concept is an offline process experiment. It does not authorise a broker session.

## Invariants

- R.56, R.59, R.60, and R.61 source gates still contain `REAL_SESSION_SOURCE_ENABLEMENT = False`.
- R.56 `one_session.consumed` is present, 10 bytes, SHA-256 `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c`.
- `one_session.permit` is absent. No new permit was written.
- R.61 archive is unchanged: 27255 bytes, SHA-256 `43b0acc351fb6292535ef4f86063fe4e95b6a66c9c5a8baf715f2ba93f62ab86`.
- No `.env` read, no OANDA host, no order, no strategy change, no broker change, no risk-control change.
- `REAL_NETWORK_EXECUTION_NOT_TESTED`. Production trading remains NO-GO.

## Dependency and source audit

The package uses the Python standard library and, on Windows, `kernel32`. It does not import `forex_bot`, `dotenv`, `requests`, `httpx`, the diagnostic supervisor, or the live-session gate. A source scan in `test_poc_sources_do_not_touch_trading_or_credentials` checks the four modules other than the test file itself. Payloads are the mode name and the files `side.txt`, `ready.txt`, and `grand.txt`.

The archive `R62_POC_SOURCE_REVIEW.zip` contains only those modules and the test. It does not contain permits, diagnostic logs, or trading code.

| Member | Bytes | SHA-256 |
| --- | --- | --- |
| `synthetic_worker.py` | 1154 | `9463c91496b9d090d2e84e3bac5b338df0b9dd737c7aa7710a676bae440f9de3` |
| `win_containment.py` | 15268 | `fdcf1bf90e32ad7f4d0910af5bae2ba969dbd47d18b1b3bd915cb048bf01e5ba` |
| `linux_containment.py` | 7209 | `f09aa55ac5291f56f2b56c7beae5956fb6aa1c549d79a846084cc09bd4a1e21c` |
| `owner_crash.py` | 2646 | `bb80b7c86bb2dfeb0af43ba6059df631de4818f21b506c96d41edf66f00a873f` |
| `test_contained_launch.py` | 13377 | `46bcefc724e97145a5063c1148815db116734a036835f3c824f6b1edb1deeff7` |

Archive size 10692 bytes. SHA-256 `6cde480eacf8fc4812e11041ae23860366743d38b5f2cdc8333128509a80ce49`.

## Network and credentials

No socket is opened. No account id, token, or `.env` path is read. The synthetic worker sleeps or writes a local file. The pipe test writes the byte `X`.

## Process escape

Windows, this host: the tested worker and its ordinary grandchild died with the job when the last handle closed. The job handle is marked non-inheritable. `JOB_OBJECT_LIMIT_BREAKAWAY_OK` is not set. A duplicated job handle is an escape from a single `CloseHandle`: the tree stayed alive until the duplicate closed. That case is a cleanup failure, not a silent success.

The file-IPC create uses `bInheritHandles` false. The pipe test inherits the read end and `NUL` stdout and stderr so the write can block. Inheriting those handles is limited to that test.

Linux, this WSL2 user: there is no cgroup for the tree. Owner exit does not kill the worker or the grandchild. That is an observed escape. The harness kill that follows is recorded as intervention and is not a containment success. `killpg` was not substituted in.

A PID read from `grand.txt` can be reused by the operating system after the real grandchild exits. The Windows tests also check the process handle's exit code. The Linux survival check uses `/proc/<pid>/stat` and can be confused by reuse if the check is late. The checks run immediately.

## Remaining surfaces

- `CreateProcess` and `fork` can still complete after a caller has given up, if a future change adds a timeout thread. This package does not add one.
- A crash after create and before job assignment is untested and can leak a suspended process.
- Real handle exhaustion was not induced. The assignment-failure test raises a simulated `OSError`.
- Explicit breakaway creation was not attempted.
- Nested jobs were observed where this interpreter is already in a job. Other parent-job policies were not surveyed.
- WSL2 is not bare-metal Linux.
- Nothing here is wired into the diagnostic supervisor. Doing so would be a new stage and is not approved.

`R62_DESIGN_REVIEW_PASS` applies to the architecture comparison and the ownership model, with the unresolved items left explicit. `R62_POC_INCOMPLETE` applies to the experiment as a whole.

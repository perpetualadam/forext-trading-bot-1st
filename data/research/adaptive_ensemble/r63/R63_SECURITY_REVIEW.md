# R.63 security review

The package is an offline process experiment. It does not authorise a broker session, and it is not integrated into the diagnostic supervisor.

## Invariants

- R.56, R.59, R.60, and R.61 source gates still contain `REAL_SESSION_SOURCE_ENABLEMENT = False`.
- R.56 `one_session.consumed` is present, 10 bytes, SHA-256 `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c`.
- `one_session.permit` is absent.
- R.61 archive is unchanged: 27255 bytes, SHA-256 `43b0acc351fb6292535ef4f86063fe4e95b6a66c9c5a8baf715f2ba93f62ab86`.
- R.62 archive is unchanged: 10692 bytes, SHA-256 `6cde480eacf8fc4812e11041ae23860366743d38b5f2cdc8333128509a80ce49`.
- No `.env` read, no OANDA host, no order, no strategy change, no broker change, and no risk-control change.
- No `sudo` and no system cgroup or systemd configuration change.
- `REAL_NETWORK_EXECUTION_NOT_TESTED`. Production trading remains NO-GO.

## Dependency audit

The package uses the Python standard library, `kernel32` on Windows, and `libc.so.6` `prctl` on Linux. It does not import `forex_bot`, `dotenv`, `requests`, `httpx`, the diagnostic supervisor, or the live-session gate. `test_sources_do_not_touch_trading_or_credentials` scans the implementation modules.

Payloads are a mode name and the files `side.txt`, `ready.txt`, and `grand.txt`. The pipe test writes the byte `X`.

## Archive

`R63_POC_SOURCE_REVIEW.zip`, 18837 bytes, SHA-256 `046f769a9a40394de6a378354905b74e714be6635529d276cf13d96aaaf736a8`.

| Member | Bytes | SHA-256 |
| --- | --- | --- |
| `capability_probe.py` | 1099 | `13e6a5c71dc93cef526a1017466dd2e004a7284cdfa9dfdf5cca50ed9abf311d` |
| `lifecycle_contract.py` | 6501 | `2a2d57346f775fea82f5d94e073404c2d8d1cabd918c19f74924c29013ffc145` |
| `linux_backend.py` | 13681 | `d02b8239365329c8e899d6cb706c6f2b08bd9259752198cf3d8e61c475ae6987` |
| `owner_crash.py` | 3326 | `c20b929163eba9353a592574c05140f1987cc3906b99303e30ec4823ee116b50` |
| `synthetic_worker.py` | 1263 | `c476e4d00a48a3c1e3acfed28159dea599ffab632f8744ee74af1205b1098921` |
| `test_lifecycle_contract.py` | 1950 | `c642a6261b11b3a4239350a86c756661cbdc9003a05ea6b4189573e42bae060d` |
| `test_linux_containment.py` | 5212 | `c9b980ea98646628a2ea7a766804c2cdca93c1309a9a7519e60083de554d6b8d` |
| `test_windows_containment.py` | 11655 | `a90e18cf07ca52ccde19d705d0d8cdaed9ad62d5a1ad7991f5b11a1293e19e59` |
| `windows_backend.py` | 23384 | `d9ea7041b39c8c97264b582c725ce34d07544a30f39a07270600c4aabfd8ba7b` |

The reports that quote this hash are not members of the archive.

## Process escape

On this Windows host the public path assigns the job at creation, confirms membership, and keeps the job handle non-inheritable. Owner exit after that assignment ended the suspended worker. Owner exit after resume ended the worker and the ordinary grandchild. A duplicate job handle is an escape from a single close: the worker stayed active and the status stayed `CLEANUP_INCOMPLETE`.

The legacy helper, which is not on the public path, still leaks a suspended process when the owner exits before assignment. The test leaves that leak visible and the harness removes the process afterwards.

The pipe test inherits the read end and `NUL` for the standard handles so the write can block. The job handle itself is not inheritable.

On this WSL2 user there is no cgroup. The default policy does not exec. The explicit policy is labeled `DIRECT_CHILD_ONLY`. Owner exit killed the direct child and left the grandchild. The harness kill is intervention, not containment.

A PID read from `grand.txt` can be reused. Windows checks also use the process handle. Linux checks `/proc/<pid>/stat` immediately. pidfd is the direct-child identity across reuse. It does not cover the grandchild.

## Remaining surfaces

- A blocked `CreateProcess` or `fork` can still complete after a caller that stops waiting. This package does not add a timeout thread around either call.
- A crash inside `CreateProcess`, before creation-time assignment finishes, was not injected.
- The two-step assign sequence still leaks and must not be revived in the supervisor.
- Real handle-table exhaustion was not induced. The rejected-attribute test is a fail-closed attribute error.
- Explicit breakaway creation was not attempted. Breakaway was not enabled on the job.
- Nested creation-time assignment was observed where this interpreter is already in a job. Other parent-job policies and Windows Server were not surveyed.
- cgroup placement was not executed. A delegated host, a VPS, and a container were not tested.
- WSL2 is not bare-metal Linux.
- Nothing here is connected to trading, credentials, or the diagnostic supervisor.

`R63_DESIGN_REVIEW_PASS` applies to the contract, with the untested environments left explicit. `R63_POC_INCOMPLETE` applies to the experiment as a whole.

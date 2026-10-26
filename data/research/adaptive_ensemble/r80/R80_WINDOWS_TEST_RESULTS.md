# R.80 Windows test results

Interpreter: CPython 3.13.5, MSC v.1943 64 bit.
Operating system: Windows.
Journals: disposable temporary SQLite files created by the tests. Production journals were not opened.
No test contacted OANDA. No PostgreSQL connection. No credential read. `one_session.permit` was not created.

| Suite | Command | Result | Runtime | Cycle | Synthetic write | Blocked write | Permit consumed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R.80 | `python -B data/research/adaptive_ensemble/r80/poc/test_r80_authorised_concurrency.py` | 17 passed, 0 failed, 0 errors, 0 skipped | 10.989s | Yes, tests 14, 16, 17 | Yes, OrderCreate and PositionClose on the fixture | Yes, stale, cold, and post-loss paths | Yes, pause tests read `network_permit=1` |
| R.79 | `python -B data/research/adaptive_ensemble/r79/poc/test_r79_operational_cycle.py` | 17 passed | 5.761s | Yes | Fixture only | Yes | As in the R.79 tests |
| R.78 | `python -B data/research/adaptive_ensemble/r78/poc/test_r78_liveness_and_protocol.py` | 21 passed | 2.638s | No unrestricted `run_bot` | No live order | Repair and fence refusals | No new live permit |

`R80_R79_REGRESSION_PRESERVED`: PASS.
`R80_R78_REGRESSION_PRESERVED`: PASS.

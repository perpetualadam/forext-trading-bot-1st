# R.82 security review

This is an offline review of the R.82 tests and the one classifier change. It is not a production penetration test.

| Control | Result |
| --- | --- |
| Isolation imported before operational modules | Present in the test module and `race_worker.py` |
| Real broker request | Not observed. Unexpected write types raise `IsolationBreach` |
| Credential read | Not performed. `.env` was not opened |
| PostgreSQL | Not contacted. `psycopg2.connect` remains blocked by the harness |
| Production journal | Not opened. Tests use `tempfile.TemporaryDirectory` |
| `one_session.permit` | Absent. `tearDown` asserts absence |
| Consumed marker | Hash checked. Body not printed. File not modified |
| Live gates | Remain false. Hashes match R.81 |
| Permit release | No test or code path resets `network_permit` from 1 to 0 |
| Client-id reuse | `test_12` reuses a client and gets `JournalUnavailable` |
| Negative closed units | Rejected before they can increase `confirmed_units` |
| Synthetic response treated as OANDA proof | Not done. Reports label the bodies as synthetic |
| Automatic retry | Not added. Ambiguous and partial rows block a second send |
| New submission protocol | Not added |

The remaining race is recorded in `R82_FINAL_CHECK_TO_REQUEST_RACE.md`. It allows one in-flight request after the check has passed. It does not authorise a second request.

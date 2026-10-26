# R.85 Security Review

Scope: the R.85 offline diff. No credentials were requested or printed. The real account id was not written into the tests, reports, or fixtures. The synthetic account is `001-002-0000001-003`.

## Boundaries held

- Isolation is imported before operational modules in the R.85 test and worker.
- Unexpected request types raise `IsolationBreach`.
- `OrderCreate` and `PositionClose` are recorded. The cycle and the races did not add a second write.
- Temporary journals only. `acknowledge_empty=True` was used for the test journal.
- The consumed marker was hashed, not printed.
- `one_session.permit` stayed absent.
- Gates stayed `REAL_SESSION_SOURCE_ENABLEMENT = False`.
- No new broker endpoint was added. The write sinks in `oanda_exec.py` were not edited.
- No lease and no automatic recovery takeover were added.

## Fail-closed changes

The epoch check inside `finalise` refuses a durable state change after a successor has committed. The second entry fence refuses publication after that successor. The quarantine exposure check refuses a new entry while an unresolved close or a quarantined row exists. A different transaction id cannot replace a stored confirmation.

## Residual

The OS lock does not span the later cycle. A check that has already succeeded is not atomic with a later `api.request`. That remains the carried `FINAL_CHECK_TO_REQUEST_RACE_REPRODUCED` item. SQLite `BUSY` and `LOCKED` on the production WAL authority read remain unreproduced. Offline tests do not prove broker idempotency.

The portfolio total can omit quarantined units. That understates a displayed exposure. It does not authorise management.

No production journal was opened. No PostgreSQL connection was made. No network broker call was made.

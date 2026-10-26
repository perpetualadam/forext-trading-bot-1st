# R.74 Test Results

Windows CPython 3.13.

- `test_r74_journal.py`: 20 tests, 20 passed, 2.591s on the passing run.
- `test_r74_close_recovery.py`: 9 tests, 9 passed, 0.832s.
- The intent-fault test was included in that 9. It recorded no `PositionClose` after a committed submission intent.
- Two subprocesses: one reservation succeeded and one was refused.
- One subprocess committed intent and exited. The parent recovered `CLOSE_OUTCOME_AMBIGUOUS` and could not reserve again.
- Synthetic full fill deleted only the matching instance. A replacement EUR_USD row remained.
- Synthetic partial fill of 400/1000 did not delete and did not submit a second close.
- Timeout followed by reopening the journal did not submit a second close.
- Missing journal and unacknowledged bootstrap recorded no broker call.
- Flat `{"positions": []}` stayed `COMPLETE_EMPTY` and retained the live row. `{}` raised `INCOMPLETE`.

WSL CPython:

- `test_r74_journal.py`: 20 passed, 1.551s.
- `test_r74_close_recovery.py`: failed at `forex_bot/oanda_client.py` line 13, `ModuleNotFoundError: No module named 'oandapyV20'`.
- Nothing was installed.

Historical suites were not edited:

- R.71: 8 passed.
- R.72: 36 passed, 1 failed. The failure is the `positions.py` hash pin.
- R.73: 8 passed, 21 failed, 2 errors. Failures are `missing_journal` / `CLOSE_NOT_REQUESTED` because those tests do not bootstrap a journal.
- R.70: 25 passed, 1 failed. The empty snapshot no longer drops the live row.
- R.68: 27 passed, 2 failed, 1 error, 1 skipped. The error is a source scan for `posmap.pop`, which R.74 removed.
- R.69: 46 passed, 2 failed, 1 skipped.

The historical suite is not green.

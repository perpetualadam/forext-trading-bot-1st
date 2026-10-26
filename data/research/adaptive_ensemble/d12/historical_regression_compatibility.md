# Historical regression compatibility

| Module | Result |
| --- | --- |
| D.2 | EXECUTED_PASS, inside 170 passed in 44.05s |
| D.3 | EXECUTED_PASS, same run |
| D.4 | EXECUTED_PASS, same run |
| D.5 | HISTORICAL_HASH_PIN_CONFLICT, 15 errors, app.py pin |
| D.6 | HISTORICAL_HASH_PIN_CONFLICT, 12 errors, app.py pin |
| D.7 | EXECUTED_PASS, same 170 |
| D.8 | HISTORICAL_HASH_PIN_CONFLICT, 7 errors, database.py pin |
| D.9 | EXECUTED_PASS, same 170 |
| D.10 | HISTORICAL_HASH_PIN_CONFLICT, 14 errors, pre-fix telegram_control.py pin |
| D.11 | EXECUTED_PASS, same 170 |
| Safety-repair | EXECUTED_PASS, 23 passed in 4.63s, separate process |

Historical hash conflicts are not passes. The full suite was not run. Production source was not modified.

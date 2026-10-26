# D.11 historical regression compatibility

| Module | Result |
| --- | --- |
| D.2 preservation | EXECUTED_PASS, part of 139 passed in 13.96s |
| D.3 activation defaults | EXECUTED_PASS, same run |
| D.4 startup preflight | EXECUTED_PASS, same run |
| D.5 lifespan | HISTORICAL_HASH_PIN_CONFLICT, 15 errors, app.py pin `f38c304c4692c4a69e537610173e5691c03d49e24c48d6e258f56d1be75ae7b4` |
| D.6 cleanup | HISTORICAL_HASH_PIN_CONFLICT, 12 errors, same app.py pin |
| D.7 cleanup | EXECUTED_PASS, same 139 |
| D.8 concurrency | HISTORICAL_HASH_PIN_CONFLICT, 7 errors, database.py pin `74bb9f5d692ace88bff525f334d7eb8577427bfe75cf5f229f647e60b88979e9` |
| D.9 concurrency remediation | EXECUTED_PASS, same 139. The D.11 child also observed one connection id and connect delta 1. |
| D.10 defect detection | Pre-fix EXECUTED_PASS, 14 passed in 9.79s. Post-fix HISTORICAL_HASH_PIN_CONFLICT, 14 errors, because the tests still pin the pre-fix Telegram hash. Those assertions were not edited and are not post-fix acceptance. |
| Safety-repair | EXECUTED_PASS, 23 passed in 4.83s, in a separate pytest process |

Historical hash conflicts are not passes. The full suite was not run.

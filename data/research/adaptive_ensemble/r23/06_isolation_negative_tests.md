# Negative isolation tests

All 15 R.23 tests passed in the isolated runner. The production application was not started.

| Case | Result |
|---|---|
| Store absent | Read raises and recovery fail-closes |
| Store corrupt | Read raises |
| Store truncated | Read raises |
| Store unreadable | Read raises |
| Store write failure | Insert returns false and fail-closes before dispatch |
| Path traversal | Arm refused, no file created |
| Path outside the approved roots | Arm refused, recovery fail-closes |
| Stale `EXEC_ORDER_OFFLINE_STORE` | Selection returns none |
| Production context with an eligibility flag | Arm refused; the flag is ignored |
| Synthetic decision on the production adapter | `synthetic_context_rejected`, broker stub not called |
| Forged production eligibility | Adapter returns without a broker call |
| Reused decision | `decision_already_used` |
| Recovered FILLED | Separate process blocks, zero dispatches |
| Recovered UNRESOLVED | Separate process blocks, zero dispatches |
| Duplicate client-order id | Read raises |

`confirm_exposure_flat` still returns false. `main.py`, `app.py`, and `oanda_exec.py` do not arm the store and do not read the environment variable.

# R.81 pre-fix rate-limit reproduction

Evidence class: executed tests against the R.80 source, before the R.81 recheck was added.

Command:

```text
python -B data/research/adaptive_ensemble/r81/poc/test_r81_rate_limit_and_recovery.py RateLimitTests.test_02_entry_authority_lost_during_rate_limit_sends_nothing
python -B data/research/adaptive_ensemble/r81/poc/test_r81_rate_limit_and_recovery.py RateLimitTests.test_03_close_authority_lost_during_rate_limit_sends_nothing
```

Interpreter: CPython 3.13.5 on Windows. The child completed real `execute_startup_sequence`, claimed the one-shot permit, passed the R.80 check, and blocked inside `acquire_oanda_rest_slot`. The parent then completed a successor `execute_startup_sequence`, which incremented the fencing epoch, and released the barrier.

The rate limiter itself was not modified. The barrier is a test wrapper around `acquire_oanda_rest_slot`. The operational sink still built the request and called `api.request`.

## Entry

The durable row already had `network_permit=1` while the child was blocked. After release the synthetic recorder count was 1. The assertion `count == 0` failed. The child printed `refused=entry_not_finalisable` only after that OrderCreate had been recorded. The successor startup had already marked the in-flight entry unresolved, and the stale owner still sent the request.

`R81_ENTRY_RATE_LIMIT_RACE_REPRODUCED`: PASS. This PASS means the defect was reproduced, not that the pre-fix code was safe.

## Close

The close row already had `network_permit=1` while the child was blocked. After release the recorder count was 1 and the child printed `close_state=CLOSE_FULLY_CONFIRMED`. A stale owner confirmed a synthetic close after the successor had taken the epoch.

`R81_CLOSE_RATE_LIMIT_RACE_REPRODUCED`: PASS, with the same meaning. The pre-fix result is a safety defect. It was not hidden.

No OANDA host was contacted. The recorder is a local SQLite file.

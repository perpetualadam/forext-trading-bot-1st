# R.73 Concurrency Review

Windows tests used `threading.Event` and `threading.Barrier`, not sleeps, as the proof.

| Case | Result |
| --- | --- |
| Two threads, one symbol | One `PositionClose`. The second call observed a non-confirmed state while the first request was held |
| Two symbols | Two `PositionClose` calls. The EUR_USD operation reached full confirmation |
| Second trigger after a timeout | Same operation id. Submission count stays 1 |
| Identity change before verification completes | `identity_changed`, reconciliation required, no delete |

The lock is not held during the HTTP call. It is not a position-store lock. The restart map is process memory only.

Unresolved: a crash after the broker accepts the close and before the operation is updated loses the blocker. The next process can submit again. That is the restart limit, not an in-process double submit.

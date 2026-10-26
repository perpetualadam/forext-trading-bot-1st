# R.79 Operational One-Cycle Integration

Evidence class: executed operational integration on Windows and Linux.

Command, from the repository root:

```text
python -B data/research/adaptive_ensemble/r79/poc/test_r79_operational_cycle.py
```

Linux used the disposable interpreter and `TMPDIR=/tmp`. Result on both platforms: 17 passed.

`test_01_real_cycle_follows_empty_startup` calls the real `run_startup_and_one_iteration` with `broker_view={"snapshot": "COMPLETE_EMPTY", "trades": []}` and symbols `["EUR_USD"]`.

| Evidence | Observed |
| --- | --- |
| Startup result | `RECOVERY_COMPLETED` |
| `_execute_bot_cycle` invocations | 1, counted by a wrapper that calls the original |
| `last_bot_cycle_utc` | Present after the original function returns |
| Management | `live_management_permitted()` true only after that completed recovery |
| Broker writes | None |
| Permit file | Absent |
| Source gate | Unchanged |

`test_02` uses snapshot `INCOMPLETE`. Recovery returns `RECOVERY_BLOCKED`, the real cycle still runs, and management stays false.

`test_07` completes recovery and then calls `_submit_order_create`. The synthetic broker records `OrderCreate` and raises. The operational classifier reports `AMBIGUOUS_TRANSPORT_OUTCOME`. The call list contains one OrderCreate.

`test_11` completes recovery, increments the durable fencing epoch, and then calls the original `_execute_bot_cycle` directly. Management is false. No write is recorded. The timestamp is set again, which shows the real function ran after authority loss.

`test_14` replaces the temporary journal with non-SQLite bytes. Startup returns blocked, the cycle still runs, and management stays false.

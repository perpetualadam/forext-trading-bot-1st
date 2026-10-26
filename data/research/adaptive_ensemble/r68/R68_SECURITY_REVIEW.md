# R.68 security review

Commit `d080d897945bc44fa37c02caab504ed707146bec`. The branch was not changed. The dirty working tree was not cleaned or reset.

## Gates and activation

| Check | Result |
| --- | --- |
| `data/research/adaptive_ensemble/r56/phase6_connection_enablement/live_session_gate.py` | `REAL_SESSION_SOURCE_ENABLEMENT = False` |
| `data/research/adaptive_ensemble/r59/live_session_gate.py` | `REAL_SESSION_SOURCE_ENABLEMENT = False` |
| `data/research/adaptive_ensemble/r60/live_session_gate.py` | `REAL_SESSION_SOURCE_ENABLEMENT = False` |
| `data/research/adaptive_ensemble/r61/live_session_gate.py` | `REAL_SESSION_SOURCE_ENABLEMENT = False` |
| `one_session.permit` | Absent |
| `one_session.consumed` | Present, size 10, SHA-256 `e1def82ee9ebd5e3d4663a1211b628a0ab2d9fffe9f2cbf63d2c5aceeadb803c`. Body not printed. File not rewritten. |

## Broker isolation

`main.py`, `forex_bot.app`, and `run_bot` were not started. No OANDA request was made. `.env` was not opened. PostgreSQL was not contacted. No migration ran.

The R.68 test process imported `forex_bot.positions` and `forex_bot.execution` only. `forex_bot.config` was not loaded.

`oanda_exec.py` still contains the only `PositionClose(` call and its hash is unchanged. The edited files contain no `PositionClose(`, `OrderCreate(`, or `TradeClose(`.

## Reachability after the patch

| Question | Evidence |
| --- | --- |
| `log_only` cannot create a close-capable import | `import_position_from_broker` writes `broker_observations` and sets `observation_only`. Tests 1 and 14. |
| Broker-mode discovery cannot grant authority | Caller `execution_kind="live"` is ignored. Test 2. |
| `auto_fix` cannot bypass the boundary | Source skip before `account_disappeared_broker_position`, and that helper returns before pop. Tests 3 and `test_disappear_path_refuses_observation_before_pop`. The reconcile module was not executed. |
| Observation cannot reach `PositionClose` through the manage prefix | Source return precedes `execute_trade(`. Test 8. The coroutine was not executed. |
| Observation cannot be locally deleted by the manage delete functions | Tests 10, 11, 21, 22, 24. |
| Forged `live` does not grant ownership | Test 25, while `observation_only` remains true. |
| Manual broker position stays outside close authority | It is stored only as an observation. Test 13. |
| Paper behaviour for an already open paper row | Predicate true. Case B no longer displaces. Test 27. |
| Bot-created management where the row is a permitted kind and `observation_only` is false | Test 15. The manage tail after the predicate was not executed. |
| New entry remains blocked | Test 19. |
| No new order endpoint | Test 20 and unchanged `oanda_exec.py` hash. |

## Residual authority limit

`observation_only` is a process-local field. A later in-process writer that clears it and sets a managed kind would pass the predicate. No reconciliation path does that. `open_position` still stores the object it is given; that is the existing bot-create path.

Concurrent interleaving of reconciliation and the manage loop was not executed (`NOT_VERIFIED`).

R.67A and R.67B files were not modified. C2, C3, and C4 are recorded as amendments and are not implemented in operational code.

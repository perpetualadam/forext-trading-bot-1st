# R.76 executive summary

Classification: `R76_IMPLEMENTATION_PARTIALLY_VALIDATED`

Production trading remains `NO-GO`. R.77 was not started.

The operational source now records an entry intent before `OrderCreate`, accepts a broker trade id only from the fill's opened-trade field, persists that position before publishing it, and runs startup recovery before the management loop. An ambiguous entry is not resubmitted. Live management returns before profit protection when recovery has not reached `RECOVERY_COMPLETED` or `RECOVERY_COMPLETED_WITH_QUARANTINE`.

Windows evidence: `data/research/adaptive_ensemble/r76/poc/test_r76_entry_recovery.py` ran 72 tests, all passed. R.75 ran 13 passed. R.74 journal ran 20 passed. R.74 operational close ran 9 passed. R.71 calculations ran 8 passed.

WSL evidence: R.74 journal ran 20 passed. The R.76 suite, the R.71 suite, and `forex_bot/oanda_client.py` stop at `ModuleNotFoundError: oandapyV20`. No package was installed.

Retained limitations:

- `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`
- `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED`
- `LINUX_INTEGRATION_NOT_VERIFIED`
- `REAL_NETWORK_EXECUTION_NOT_TESTED`
- `POSTGRESQL_INTEGRATION_NOT_TESTED`
- `DATA_ONLY_MODE_NOT_PROVEN_SAFE`

`run_bot` was not started. No OANDA practice or live order was sent. No PostgreSQL connection was opened. `one_session.permit` was not created. The consumed marker hash is unchanged.

## Acceptance criteria

| Criterion | Result | Evidence |
| --- | --- | --- |
| `R76_BASELINE_VERIFIED` | Pass | HEAD `d080d897945bc44fa37c02caab504ed707146bec`, branch `main`, expected pre-edit hashes matched before R.76 edits |
| `R76_ENTRY_CALL_GRAPH_COMPLETE` | Pass | `R76_ENTRY_AND_STARTUP_CALL_GRAPH.md` |
| `R76_STARTUP_CALL_GRAPH_COMPLETE` | Pass | same report; `run_bot` lines 4498–4509 |
| `R76_DURABLE_ENTRY_INTENT_IMPLEMENTED` | Pass | `forex_bot/entry_journal.py` `begin_entry_submission` |
| `R76_ENTRY_INTENT_COMMITTED_BEFORE_NETWORK` | Pass | tests 16 and 17 |
| `R76_ENTRY_AMBIGUITY_BLOCKS_RETRY` | Pass | tests 22, 23, 24, 34 |
| `R76_BROKER_ORDER_ID_NOT_TREATED_AS_TRADE_ID` | Pass | tests 02 and 28 |
| `R76_VERIFIED_TRADE_ID_CAPTURED` | Pass | `tradeOpened.tradeID` in `classify_entry_response` |
| `R76_ENTRY_EVIDENCE_ATTRIBUTION_VERIFIED` | Pass | tests 01–15 |
| `R76_DURABLE_POSITION_CAPTURE_IMPLEMENTED` | Pass | `record_entry_response` then `persist_bot_position` |
| `R76_POSITION_PERSISTED_BEFORE_MANAGEMENT` | Pass | test 28 |
| `R76_ENTRY_CRASH_RECOVERY_IMPLEMENTED` | Pass | tests 22–24 and 34–37, process restart via journal reopen |
| `R76_STARTUP_RECOVERY_INTEGRATED` | Pass | `run_bot` calls `execute_startup_sequence` before `while True` |
| `R76_RECOVERY_BEFORE_MANAGEMENT` | Pass | tests 38 and 39 |
| `R76_BROKER_ONLY_OBSERVATIONS_NOT_PROMOTED` | Pass | tests 42–44 and 72 |
| `R76_MISSING_PROTECTION_STATE_QUARANTINED` | Pass | tests 30 and 54 |
| `R76_PROFIT_PROTECTION_STATE_PRESERVED` | Pass | tests 51–53 and 69 |
| `R76_RATCHET_MONOTONIC_AFTER_RESTART` | Pass | test 55 |
| `R76_MULTIPROCESS_ENTRY_SINGLE_FLIGHT` | Pass | test 20, one synthetic `OrderCreate` |
| `R76_R75_UNIVERSAL_CLOSE_GUARD_PRESERVED` | Pass | test 61 and R.75 13 passed |
| `R76_R74_DURABLE_CLOSE_JOURNAL_PRESERVED` | Pass | R.74 journal 20 and operational 9 |
| `R76_R73_TRANSACTION_MATCHING_PRESERVED` | Pass | tests 64 and 65; historical R.73 suite is not green |
| `R76_R72_PROTECTION_EVIDENCE_PRESERVED` | Pass | test 66; `broker_protection.py` hash unchanged |
| `R76_R70_SNAPSHOT_CONTRACT_PRESERVED` | Pass | test 67; `reconciliation.py` hash unchanged |
| `R76_R68_OWNERSHIP_PRESERVED` | Pass | test 68 |
| `R76_R71_PROFIT_PROTECTION_UNCHANGED` | Pass | hash `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f` |
| `R76_ENTRY_GATES_UNCHANGED` | Pass | test 70; one `execute_oanda_market_open` call site; adapter still withheld |
| `R76_SOURCE_GATES_UNCHANGED` | Pass | `REAL_SESSION_SOURCE_ENABLEMENT = False` |
| `R76_NO_REAL_NETWORK_EXECUTION` | Pass | synthetic clients only; `run_bot` not started |
| `R76_NO_POSTGRESQL_CONNECTION` | Pass | no migration or database client was used |
| `R76_NO_PERMIT_CREATION` | Pass | zero `one_session.permit` files |

Explicit answer:

The operational bot can establish a verified broker trade id after a synthetic entry, durably store bot ownership and the initial management state, recover an ambiguous entry without resubmitting it, and refuse live management until recovery finishes.

- Implemented in operational source: yes.
- Verified offline on Windows: yes, 72 R.76 tests.
- Tested across process restarts: yes, journal reopen and the entry worker.
- Tested across independent processes: yes, one `OrderCreate` in test 20 and a blocked second recovery in test 48.
- Broker-tested: no.
- Not verified: broker-enforced idempotency, SQLite power-loss durability, Linux operational import, PostgreSQL, and data-only mode.

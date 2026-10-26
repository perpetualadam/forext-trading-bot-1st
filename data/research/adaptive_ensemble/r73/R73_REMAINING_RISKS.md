# R.73 Remaining Risks

| Item | Status |
| --- | --- |
| R66-03 `broker_sl_tp_hit` returns false | Open. A pending or referenced stop still does not request this close |
| R66-07 account-currency sizing | Open. Untouched |
| R66-10 delete without matched units | Narrowed for the live manage path and the flat-snapshot path. A process restart can still lose the blocker and allow another submission |
| R66-11 ambiguous close identity | Narrowed inside one process. Not durable. Not broker-enforced |
| R66-16 reconciliation versus management | Open. Flat retention does not reconcile units back into the local row |
| Restart | `RESTART_DURABLE_IDEMPOTENCY_NOT_IMPLEMENTED` |
| Broker duplicate suppression | `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED` |
| Linux | `LINUX_INTEGRATION_NOT_VERIFIED` |
| Broker network | `REAL_NETWORK_EXECUTION_NOT_TESTED` |
| PostgreSQL | `POSTGRESQL_INTEGRATION_NOT_TESTED` |

`backtest.py` can still call `execute_trade` with a live kind. `close_position` will then refuse to drop the row. That path was not given a new close trigger.

A confirmed rejection allows a later new operation. An ambiguous close does not.

# R.74 Executive Summary

Classification: `R74_IMPLEMENTATION_PARTIALLY_VALIDATED`

Also stated:

- `RESTART_DURABLE_RECOVERY_NOT_FULLY_VERIFIED` for a kill during the SQLite commit syscall. Process exit after a returned commit was tested.
- `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`
- `LINUX_INTEGRATION_NOT_VERIFIED` for the operational close path. The journal suite passed under WSL. The operational suite stopped at `import oandapyV20`.
- `REAL_NETWORK_EXECUTION_NOT_TESTED`
- `POSTGRESQL_INTEGRATION_NOT_TESTED`
- Production trading remains `NO-GO`.

R.74 adds a local SQLite close journal and an identity-bound delete. A live close now commits a reservation, then commits submission intent, and only then may call the existing position-close helper. A missing, corrupt, or unacknowledged journal does not submit. A confirmed fill deletes the local row only when the current row is still the same position instance.

The in-memory position book is not durable. Local SQLite locking is one machine, not a shared cluster. OANDA was not contacted.

## Answer

Can the operational bot now survive a process crash or restart without losing an unresolved broker-close operation, prevent a second process from submitting the same close, and guarantee that a confirmed fill cannot delete a different local position?

| Claim | Result |
| --- | --- |
| Implemented in source | Yes, on the guarded live path |
| Verified offline | Yes, Windows CPython 3.13, synthetic broker and temporary SQLite |
| Tested across actual process restarts | Yes, for rows already committed. A subprocess reserved or committed intent and exited. The next process recovered the row and refused another reservation |
| Tested across processes | Yes, for the reservation. Two subprocesses raced. One reserved and the other was refused. Two processes were not both pointed at the synthetic broker |
| Broker-tested | No |
| Not verified | Linux operational import, PostgreSQL, real OANDA, cross-machine locking, and a crash inside the commit fsync |

A second process that ignored the journal and called the close helper directly is outside this gate. The manage path does not do that.

# R.67C Reference model

Isolated Python under `data/research/adaptive_ensemble/r67/c/poc/reference_model.py`. It does not import `forex_bot`, open a socket, or use PostgreSQL. Passing its tests does not mean the operational bot implements the contracts.

## Structure

`MemoryLedger.commit` copies observation, grant, and close maps, runs a mutator, and publishes the copy only if the mutator returns. `fail_commits` aborts before the mutator. A commit while `broker_wait` is set raises `LockAcrossIO`. That is `MODEL_TRANSACTION_TESTED`. It is not `POSTGRESQL` behaviour.

`ReferenceBook` is one process. `execution_grants` is process memory. Restart clears it and advances `process_generation`. Durable rows survive in the ledger.

Units are `Decimal`. Times used by the model are UTC. Scenarios pass `fresh` explicitly. No freshness duration is chosen.

## Identity

Each observation key is account, instrument, book side, and one trade id. `local_tracking_id` is minted by the model and is not a trade id. `close_operation_id` is minted per grant and is not the RAM key, the trade id, or a fill transaction id.

The synthetic account id is `ACC-SYNTHETIC`. The synthetic instrument is `EUR_USD`.

## Authority

| Action | Rule |
| --- | --- |
| Discover / reconcile | Observation only. Management is set false. |
| `grant_monitor` | Source must be `operator`. Both sides open refuses it. Matching fresh snapshot required. Sets management. Does not set execution. |
| `grant_close` | Source must be `operator`. Units must be greater than zero and not greater than authoritative units. Both sides open refuses it. A blocking close refuses it. Creates `CLOSE_AUTHORISED` and a process-local execution grant. Does not send. |
| `import`, `log_only`, `execution_kind`, `reconcile_import` | Recorded as refusals. No grant. |

## Exposure

| State | When |
| --- | --- |
| `OPEN` | Authoritative units greater than zero and equal to the original units. |
| `PARTIALLY_OPEN` | A later complete fresh snapshot reduced authoritative units and left a remainder. |
| `FLAT_CONFIRMED` | A closing transaction id was supplied and the prior observation had units. |
| `STALE` | The latest read was incomplete, timed out, or marked not fresh, and flat is not confirmed. |
| `CONFLICT` | Two complete reads were marked contradictory, or a stale fill disagreed with a newer snapshot. |
| `UNKNOWN` | The view has no row, or units are zero without flat confirmation. |

`exposure_zero_reported` is set when a complete snapshot says zero. Authoritative units stay at the previous positive value until the closing-transaction bar. A fill response never changes authoritative units.

## Close

Pre-send checks the grant, the snapshot, and single-flight, then commits `CLOSE_SUBMITTING` and consumes the grant. `simulate_send` is allowed only from `CLOSE_SUBMITTING`, once, and it does not commit during `broker_wait`.

| Response | State | Attribution |
| --- | --- | --- |
| Timeout or lost acknowledgement | `CLOSE_OUTCOME_UNKNOWN` | `UNKNOWN` |
| Reject, no fill | `CLOSE_REJECTED` | `UNKNOWN` |
| Fill units equal authorised units, `tradesClosed` sums to that, every trade id was granted | `CLOSE_FULLY_CONFIRMED` | `BOT_ATTEMPT_CONFIRMED` |
| Fill units greater than zero and less than authorised, same trade-id rule | `CLOSE_PARTIALLY_FILLED` | `BOT_ATTEMPT_CONFIRMED` |
| Missing `tradesClosed`, sum mismatch, unknown trade id, or price and P&L only | `CLOSE_RECONCILIATION_REQUIRED` | `UNKNOWN` |
| Fill transaction id already stored | No extra units | Unchanged |
| Fill epoch older than the committed snapshot | `CLOSE_MANUAL_REVIEW_REQUIRED` | `UNKNOWN` |
| Flat read while the attempt is unresolved and the transaction is not on the operation | `CLOSE_MANUAL_REVIEW_REQUIRED` | `UNKNOWN` |

Restart moves `CLOSE_AUTHORISED` to `CLOSE_NOT_REQUESTED` and revokes the unconsumed grant. It moves `CLOSE_SUBMITTING` to `CLOSE_OUTCOME_UNKNOWN`. It does not restore execution. A failed restart commit sets `recovery_blocked` and refuses send and new grants. The durable row stays as it was.

A blocking operation is any of `CLOSE_AUTHORISED`, `CLOSE_SUBMITTING`, `CLOSE_OUTCOME_UNKNOWN`, `CLOSE_RECONCILIATION_REQUIRED`, `CLOSE_MANUAL_REVIEW_REQUIRED`, or a partial or requested-unit fill whose remainder has not been seen on a newer snapshot. Clarification C3.

## Protection

`local_stop_reference` and `confirmed_broker_stop_price` are different fields. A fallback price sets `LOCAL_REFERENCE_ONLY` and does not copy into the confirmed price. `BROKER_PROTECTED` requires a complete stop section, an order id, and a price. `UNPROTECTED_CONFIRMED` requires a complete stop section with no stop. An incomplete section stays `PROTECTION_UNKNOWN`. A non-fresh read of a prior broker or unprotected confirmation becomes `PROTECTION_STALE`. Restart does the same for verified states and leaves a fallback as `LOCAL_REFERENCE_ONLY`.

## Retirement

`retire` commits only when `flat_confirmed` is true, the snapshot is fresh and complete, the row is not in conflict, and no blocking close holds `pending_close_id`. Otherwise it returns false and the row stays.

## Contract map

| Contract rule | Model |
| --- | --- |
| Import is observation | `discover` and non-operator grants |
| Management is not execution | monitor grant has no send path |
| Pre-send before bytes | `simulate_send` rejects `CLOSE_AUTHORISED` |
| Timeout is not success or rejection | `timeout` and `lost_ack` |
| Local fallback is not broker protection | separate fields |
| Restart clears execution | `execution_grants` cleared |
| Reconcile does not clear a pending close | reconcile leaves `pending_close_id` |
| Both sides block management | `_both_sides_open` |
| Entry path | Not represented. The model cannot open a trade. |

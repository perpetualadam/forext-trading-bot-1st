# R.85 Exposure Data Model Audit

Evidence: source inspection of `positions.py`, `position_recovery.py`, `startup_recovery.py`, `close_journal.py`, `entry_journal.py`, `broker_close_evidence.py`, `oanda_exec.py`, `bot_loop.py`, and `profit_protection.py`. Executed confirmation is in `test_03` and `test_04` on a disposable journal.

## Quantities

| Quantity | Where it lives | Class | Meaning |
| --- | --- | --- | --- |
| `original_units` | `managed_positions.units` | Durable | Entry quantity. Not rewritten by a partial close. |
| `confirmed_closed_units` | `close_operations.confirmed_units` | Durable | Units verified from one close transaction. |
| `journal_remaining_units` | `close_operations.remaining_units` | Durable | `original - confirmed` for that one operation. |
| `broker_reported_open_units` | startup view `trades[].units` | Observed | Synthetic or fetched snapshot. Not a new journal column. |
| `memory_position_units` | `Position.units` | In-memory | Copied from the durable original row on recovery. |
| `manageable_units` | decision `manageable` | Inferred | Zero while the decision is quarantined or awaiting finalisation. |
| `quarantined_units` | `quarantined_positions` | Inferred | The recovered row, still carrying original units. |

No schema change was made. The current columns already separate original units from confirmed and remaining units.

For one position and one reduction, journal remaining equals original minus confirmed. That identity was executed: 1000, 400, and 600. It does not prove the broker still holds 600. `evaluate_durable_row` compares the snapshot with `managed_positions.units`, so 600 does not match 1000 and the reason is `units_mismatch`.

## Lifecycle

1. Entry finalisation writes original units and `ENTRY_FINALISED` in one journal transaction, then checks the recovery fence before `positions[symbol] = pos`.
2. A live close reserves a close operation, consumes `network_permit`, and stores confirmed and remaining units only from the transaction parser.
3. `Position.units` is not reduced to the journal remainder.
4. Startup clears the process book, classifies the snapshot, and either publishes a manageable row or stores the row in `quarantined_positions` with `recovery_quarantine` and `observation_only`.
5. A blocking close other than a not-yet-finalised full close yields `outstanding_<state>` and `manageable=False`.
6. `CLOSE_FULLY_CONFIRMED` yields `awaiting_finalisation`, also not manageable.
7. `close_confirmed_live_position` pops memory only for a full confirmation whose identity matches. With an active epoch it finalises only if that epoch is still current.

## Partial fixture actually stored

Executed on a disposable journal, BUY EUR_USD, synthetic transaction `TX-R85`:

| Field | Value |
| --- | --- |
| Durable units | 1000 |
| Confirmed | 400 |
| Remaining | 600 |
| Memory units before restart | 1000 |
| Close state | `CLOSE_PARTIALLY_CONFIRMED` |
| `network_permit` | 1 |
| Generation | 1 |
| Ratchet | 40 |
| Manageable after restart | 0 |
| Quarantine dict | one row, units still 1000 |

The same split held for SELL and for USD_JPY.

## What the model cannot do

It cannot store “reconciled current exposure is 600” as a manageable quantity without either treating 600 as the original units or adding a field. This stage did neither. The safe representation is the existing split plus quarantine.

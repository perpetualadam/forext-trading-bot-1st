# R.85 Broker Snapshot Evidence Audit

Evidence: source inspection of `load_startup_broker_view`, `BrokerSnapshotError`, and `evaluate_durable_row`. Executed startup calls used synthetic view dictionaries. Those dictionaries are not an OANDA response.

## What the startup view contains

`load_startup_broker_view` is read-only. A missing client becomes `REQUEST_FAILED` with `empty_book_is_not_flat`. One trade id and a nonzero net becomes one trade. Several trade ids become broker-only rows with empty direction and units. The class is `COMPLETE_NONEMPTY` when the detail map is non-empty and `COMPLETE_EMPTY` when it is empty.

The view does not carry:

- a retrieval timestamp
- a comparison with the close transaction time
- a pagination-complete flag
- a transaction watermark

No watermark was invented.

## How recovery treats labels

`execute_startup_sequence` blocks the whole run, without evaluating rows, when the snapshot is `INCOMPLETE`, `MALFORMED`, `REQUEST_FAILED`, `STALE`, `UNAVAILABLE`, `UNKNOWN`, or `CONFLICT`. The reason is `broker_snapshot_not_authoritative`. The OS lock is released in `finally`. The journal rows are not rewritten.

`evaluate_durable_row` applies the same non-authoritative set, then:

| Observation | Decision |
| --- | --- |
| `COMPLETE_EMPTY` | `broker_flat_unattributed`, not manageable |
| Not exactly one same-instrument trade | `multiple_or_missing_trades` |
| Account differs | `account_mismatch` |
| Trade id differs | `trade_id_mismatch` |
| Direction differs | `direction_mismatch` |
| Units differ from durable original units | `units_mismatch` |
| Units match and a partial or ambiguous close is blocking | `outstanding_<state>` |
| Units match and the close is `CLOSE_FULLY_CONFIRMED` | `awaiting_finalisation` |
| Units match and nothing is blocking | `restored_managed`, manageable |

An empty list is flat only when the label is `COMPLETE_EMPTY`. An empty `INCOMPLETE` view is blocked and is not treated as flat.

## Freshness and pagination

Freshness is `NOT_AVAILABLE` on the live view. The tests that pass `snapshot=STALE` exercise the existing refusal. They do not prove the live fetch detected staleness.

Pagination completeness is `NOT_AVAILABLE`. There is no page token in the startup view. `test_19` exercised `INCOMPLETE`, which is the existing completeness failure, and confirmed the startup module does not mention pagination. That scenario is partial coverage of the requested pagination case.

A snapshot labelled `COMPLETE` in these tests is a synthetic assumption. It is not proof the snapshot was taken after the close, or that every page was read.

## Executed consequence

Incomplete, stale, and failed snapshots left the close state unchanged and produced no `PositionClose`. A complete empty snapshot quarantined the durable row as `broker_flat_unattributed` and did not invent a fill.

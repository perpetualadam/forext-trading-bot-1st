# R.70 Snapshot Contract

These labels are strings on the reconciliation snapshot and on `BrokerSnapshotError`. They are not a new broker-state machine.

The contract applies to the operational OpenPositions path: `fetch_broker_positions_detail` → `_interpret_open_positions` → `_publish_snapshot` → `reconcile_positions_log_only`.

## Classifications

| Label | Meaning | Published | Convergence |
| --- | --- | --- | --- |
| `COMPLETE_NONEMPTY` | Body is an object, `positions` is a list, and at least one instrument survives validation with a non-zero net | Yes, if this request generation is current | Yes |
| `COMPLETE_EMPTY` | Body is an object, `positions` is a list, and every valid row has a zero net, including `[]` | Yes, if this request generation is current | Yes |
| `INCOMPLETE` | Body is an object and the `positions` key is absent | No | No |
| `MALFORMED` | Body is not an object, `positions` is not a list, or an entry fails structural or numeric validation | No | No |
| `REQUEST_FAILED` | `_oanda_request` raises, including timeout after the client's existing retries | No | No |
| `STALE` | This request's generation is no longer the current in-process generation | No | No |
| `CONFLICT` | The same instrument appears twice, or one instrument has both a positive long and a negative short | No | No |
| `UNKNOWN` | API client or account id is missing | No | No |

## Rules

1. A successful body with a list `positions` and no open nets is `COMPLETE_EMPTY`. It reports what that response contained. It does not prove that a previously submitted close filled.
2. A missing `positions` key is `INCOMPLETE`. `resp.get("positions") or []` is no longer used on this path.
3. `null`, a string, a dictionary, or any other non-list `positions` value is `MALFORMED`.
4. One malformed entry rejects the whole body. A valid sibling instrument is not published.
5. Units are parsed with `Decimal`. Blank, unparseable, and non-finite values are `MALFORMED`. Long units below zero, or short units above zero, are `MALFORMED`. Stored nets remain `float` so existing comparisons keep their type. That conversion is a precision limit, not a sizing-formula change.
6. Timeouts and other request exceptions become `REQUEST_FAILED`. They do not publish an empty book.
7. The OpenPositions client response used here has no snapshot timestamp and no broker generation id. No freshness duration was chosen. `STALE` means "an older in-process request", not "older than N seconds".
8. `_begin_snapshot_request` increments a process-local counter before the request returns. `_publish_snapshot` writes only when that generation is still current. The lock covers the counter and the publish, not the broker call and not the rest of reconciliation.
9. `INCOMPLETE`, `MALFORMED`, `REQUEST_FAILED`, `STALE`, `CONFLICT`, and `UNKNOWN` do not call `account_disappeared_broker_position`, do not delete or resize a local row, do not promote an observation, and do not send `PositionClose`.
10. A complete snapshot is evidence about exposure. `position_management_permitted` remains the management predicate. Import still sets `observation_only=True` and `execution_kind=reconcile_import`.

## Entry rules inside a list

- Each entry must be an object with a non-blank instrument.
- Any repeated instrument, including a zero-net row followed by another row for the same instrument, is `CONFLICT`.
- Both `long` and `short` must be objects with a `units` field.
- Both sides non-zero is `CONFLICT`. The units are not blended.
- A zero net is omitted from the published book after the row has passed structural validation. The snapshot can still be `COMPLETE_EMPTY`.
- A non-zero side needs a positive finite `averagePrice`.
- Missing or null `tradeIDs` become an empty list. A non-list `tradeIDs` is `MALFORMED`.
- A well-formed unknown instrument such as `FOO_BAR` stays an observation when import runs. It does not become managed.

## Explicit non-claims

- `COMPLETE_EMPTY` is not `CLOSE_FULLY_CONFIRMED`.
- `COMPLETE_EMPTY` does not satisfy R66-10 or R66-11.
- Publication of a valid book does not grant management authority.
- The account-summary adapter in `forex_bot/oanda_account_adapter.py` has its own missing-book checks. It is not this OpenPositions path.
- `forex_bot/shadow/engine.py` reads a local shadow blob with `blob.get("positions") or []`. That is saved research state, not a broker snapshot.

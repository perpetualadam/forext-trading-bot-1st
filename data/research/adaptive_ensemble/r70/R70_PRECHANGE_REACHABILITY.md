# R.70 Pre-change Reachability

This describes the operational path before the R.70 edit. It is source behaviour that was present at hash `f938807b59c2089767fdf69e4cf7d74671ffe62d74e5853169812ffe438a0bbf`. It is not an assumption about fields the client does not return.

## Call graph before the change

1. `reconcile_positions_log_only` called `fetch_broker_positions_detail`.
2. `fetch_broker_positions_detail` called `get_api()` and read `Config.OANDA_ACCOUNT_ID`.
3. A missing client in paper mode returned `{}` without a request. That empty dict could then be remembered as a broker book.
4. Otherwise it built `OpenPositions(accountID=...)` and called `_oanda_request`.
5. The response was read as `resp.get("positions") or []`.
6. A missing key and a null value both became `[]`.
7. The loop coerced units with `float`, skipped rows that failed that coercion, and combined long and short into one net.
8. The function returned the dict. On success, reconcile called `_remember_broker_snapshot` and then `_apply_position_convergence`.
9. With `RECONCILE_ACTION=auto_fix`, a permitted live row absent from that dict could reach `account_disappeared_broker_position`.
10. That helper returns `"observation"` before `posmap.pop` when the resident row fails `position_management_permitted`. A permitted live row can still be popped.

## Answers

| Question | Confirmed pre-change behaviour |
| --- | --- |
| Where is the request made? | `fetch_broker_positions_detail` via `_oanda_request` and `OpenPositions` |
| Where is the body received? | The return value of `_oanda_request` |
| Is `positions` required? | No. A missing key became `[]` |
| Must `positions` be a list? | Not checked. A null became `[]`. A string or dict usually failed during iteration and became a fetch error |
| How is `[]` interpreted? | Successful empty snapshot |
| How is a missing key interpreted? | Same as `[]` |
| How are malformed entries handled? | Unparseable units were skipped. The rest of the body could still publish |
| How are units parsed? | Float coercion, not `Decimal` |
| How are both sides handled? | Blended into one net. R.69 observed 1000 and -400 become 600 |
| How are trade IDs handled? | Collected when present. Missing IDs were tolerated |
| How is staleness detected? | It is not. No broker timestamp is read |
| How is the previous snapshot replaced? | `_remember_broker_snapshot` replaces `_last_broker_nets` unconditionally on success |
| How is `last_error` assigned? | Set from the fetch exception. A missing key produced no error |
| How are Cases A–E decided? | After a published book, in `_apply_position_convergence` |
| Where can `auto_fix` mutate a permitted live row? | `account_disappeared_broker_position` and `adjust_position_units_to_broker` for permitted broker-backed rows |
| Can another consumer treat incomplete data as flat? | This path could. The account adapter rejects a missing positions key separately. The shadow engine reads local state |
| Can an older response overwrite a newer one? | Yes. There was no generation identity |

## Destructive reachability before the change

| Evidence | `account_disappeared_broker_position` | Local delete or resize | Observation promoted | `PositionClose` |
| --- | --- | --- | --- | --- |
| Missing `positions` key | Reachable for a permitted live row when `auto_fix` is on | Reachable through that helper | No | No on this path |
| `positions: null` | Same as a missing key, because null is falsy | Same | No | No |
| `positions: []` | Reachable for a permitted live row | Reachable | No | No |
| Request exception | Not reached. Fetch error skips convergence | No | No | No |
| Both sides | Not a disappear. The blended net could be imported as an observation | No management grant | No | No |
| Observation-only row | Helper returns `"observation"` before pop | Refused by R.68 | No | No |
| Paper row | Not broker-backed, so the disappear branch does not own it | Paper row kept | No | No |

`PositionClose` is not sent by reconciliation. The disappear helper pops a permitted local row and may query trade details. That is a local destructive action without a close-fill attribution.

## After the change

Invalid evidence stops in `fetch_broker_positions_detail` or in the reconcile `except BrokerSnapshotError` branch. `_apply_position_convergence` runs only when `err is None`. A valid empty list still reaches the old disappear path. See `R70_PATCH_DESIGN.md`.

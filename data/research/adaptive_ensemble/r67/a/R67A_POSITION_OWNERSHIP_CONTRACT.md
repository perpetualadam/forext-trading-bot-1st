# R.67A Position ownership contract

Design only. The working-tree files cited by R.66 still match the R.66 hashes recorded in `R66_SECURITY_REVIEW.md`. Commit `d080d897945bc44fa37c02caab504ed707146bec`. This document does not change that source. The production entry path stays blocked (`bot_loop.py` 3323–3328 and 1125–1134). `REAL_NETWORK_EXECUTION_NOT_TESTED`. Production trading remains NO-GO.

## Source check

| R.66 claim | Rechecked source | Result |
| --- | --- | --- |
| `broker_sl_tp_hit` returns false | `live_manage.py` 76–78 | Unchanged |
| Import runs when broker mode is on, including `log_only` | `reconciliation.py` 82–84, 530–534, 638–650 | Unchanged |
| Import stores `local_fallback` prices and does not send them | `reconciliation.py` 477–516, `positions.py` 160–215 | Unchanged |
| `PositionClose` returns price and P&L, then the caller drops the whole local row | `oanda_exec.py` 435–450, `bot_loop.py` 1058–1084 | Unchanged |
| A close exception keeps the row; the next cycle can close again; the close body has no client id | `oanda_exec.py` 418–433, `bot_loop.py` 686–690 | Unchanged |
| Reconcile and `run_bot` share `positions` | `positions.py` 8–9, `app.py` 630–633 | Unchanged |
| New entries stay blocked | `bot_loop.py` 1125–1134, 3323–3328 | Unchanged |

No design below treats the current behaviour as the contract. Where the source disagrees with this contract, the mapping document names the gap. A later stage would have to change code. This stage does not.

## Three dimensions

These words are not synonyms and must not be stored in one flag.

| Dimension | Meaning | What it allows |
| --- | --- | --- |
| Observation | A read of the broker, or of a paper book, produced a record. The bot has not accepted a duty to manage it. | Store and display the snapshot. Compare it with the last snapshot. |
| Management | An explicit grant says the bot may monitor that identity and may form a request. | Update monitoring fields. Emit a close request record. |
| Execution authority | A separate grant names one broker action, one identity, and one attempt. | Send that one action. |

A close request produced by management is not execution authority. Weekend flatten, profit protection, and a true `broker_sl_tp_hit` are requests. They do not send.

## Default for an import

`import_position_from_broker` (`positions.py` 160–215) today writes a RAM row with `execution_kind="reconcile_import"` and `broker_order=True`. `is_broker_backed` treats that kind as broker-backed (`execution.py` 27–43). The contract rejects that inference.

An imported snapshot starts as observation only:

- Provenance `EXTERNAL_UNKNOWN` unless a recorded bot fill transaction matches the trade id.
- Management false.
- Execution authority false.
- Protection `PROTECTION_UNKNOWN` until a trade read supplies the evidence in the protection contract. A `local_fallback` price is `LOCAL_REFERENCE_ONLY` and is not broker protection (`R66-05`).

No source path verified in R.66 grants management or close authority safely. `live_safety.initialise_fail_closed` blocks new opens on process start (`live_safety.py` 383–405) and then exempts close (`live_safety.py` 102–106). That exemption is not a close grant. Configuration strings such as `EXECUTION_MODE`, `RECONCILE_ACTION`, and `RECONCILE_IMPORT_BROKER_POSITIONS` select I/O behaviour. They are not authority.

## Provenance classes

| Class | Evidence required | Forbidden evidence |
| --- | --- | --- |
| `BOT_CREATED` | A fill transaction for an order this bot submitted, with client id, account, instrument, side, and filled units. The production producer does not create these today (`R66-01`). | `execution_kind=live` alone |
| `EXTERNAL_UNKNOWN` | Broker snapshot of a trade or position side with no matching bot fill record. This includes human trades, another program, and unknown history. | Absence of a client id is not proof of a human |
| `MANUAL_ASSERTED` | An operator record that names the account, trade id, and the assertion. The bot does not invent this from a missing client id. | OpenPositions without that record |
| `PARTIAL_REDUCTION` | A prior verified unit count and a later broker read or fill whose closed units are smaller than that count and greater than zero | A local row deleted after an uncounted `PositionClose` (`R66-10`) |
| `OBSERVED_FLAT` | A fresh broker read shows the targeted side at zero units, plus a closing transaction id when the previous read had units | `close_position` in RAM (`bot_loop.py` 1084) |
| `PROVENANCE_UNKNOWN` | Any record that lacks account, instrument, side, or a broker identifier | A symbol key alone (`positions.py` 8–9) |
| `CLOSE_AMBIGUOUS` | A close attempt was sent or may have been sent, and no resolving read has classified it (`R66-11`) | A timeout exception by itself, which stays ambiguous |
| `BROKER_STOP_OBSERVED` | Protection state `BROKER_PROTECTED` | A numeric `stop_loss` field |
| `LOCAL_STOP_ONLY` | Protection state `LOCAL_REFERENCE_ONLY` | `sl_source=local_fallback` promoted to confirmed |

`MANUAL_ASSERTED` is not available from the current source. Assigning it without an operator record is forbidden. Whether a particular open trade was clicked by a person is `NOT_VERIFIED`.

## Permitted transitions

| From | To | Condition |
| --- | --- | --- |
| No record | Observation | A successful broker read, or a paper book that never claims to be a broker position |
| Observation | Observation | A newer snapshot of the same identity. Authority flags stay false |
| Observation | Management | An explicit `MONITOR` grant whose identity fields match the snapshot, whose grant id was not used, and which has not expired or been revoked |
| Management | Close request | A monitor rule, weekend rule, or operator request writes a request record. No broker call |
| Close request | Execution authority | A separate `CLOSE` grant names that request, the units, and one attempt id |
| Execution authority | Spent | The attempt is submitted, refused before send, or expires. One attempt consumes it |
| Spent or ambiguous | Observation update | A read-only trade or transaction read classifies the attempt |
| Any | Revoked | Operator revocation, identity mismatch, or process restart for execution authority |

## Forbidden transitions

| Forbidden step | Why | Current source that does it |
| --- | --- | --- |
| Import to management | `R66-04` | `reconciliation.py` 638–650 then the manage branch in `_evaluate_impl` |
| Import to close authority | `R66-04` | `execution_kind` selects the close path (`trading.py` 391–398, `execution.py` 232–234) |
| `broker_order=True` or a trade id to authority | Presence is not a grant | `positions.py` 209–210 |
| `execution_kind` to authority | A label is not a grant | `execution.py` 27–43 |
| Config string to authority | Mode is not a grant | `reconciliation.py` 530 |
| Management request to `PositionClose` | Request is not authority | `_evaluate_impl` calls `execute_trade` from weekend or protection (`bot_loop.py` 897–1067) |
| Local delete to `OBSERVED_FLAT` | RAM deletion is not broker evidence | `bot_loop.py` 1084, `R66-10` |
| Restart reloads a row into execution authority | `R66` found no safe restore. Orders reload (`app.py` 574–579). Positions do not. A future database row must still load as observation or as revoked execution | Not present for positions, and must not be added as a silent restore |
| Ambiguous close to a second close | `R66-11` | The next cycle can call `PositionClose` again |
| Both long and short collapsed into one managed row | One instrument is not one trade | `reconciliation.py` 270–286 blends a net and one average price |

Paper rows (`execution_kind` in `paper`, `simulated`, `window_paper`) are a local book. They are not broker observation. They must not be upgraded to broker management by a reconcile import. The current Case B displace (`reconciliation.py` 537–560) replaces a paper row with an import. Under this contract that import is observation only and must not inherit the paper row's management.

## Shared book

`R66-16`: `run_bot` and `reconciliation_loop` both use `positions`. This contract splits the book into an observation record and an authority record. Reconciliation may replace observation fields. It must not write management or execution grants. The trading loop may read both and may append a request. It must not grant itself authority. One writer owns authority records. The current unlocked dict cannot express that split. The design does not add a lock in this stage. It defines the rule a later implementation has to meet.

## What this contract does not do

It does not open the production entry path. It does not send a stop when protection is missing. It does not choose sizing, distances, or strategy. It does not integrate R.62–R.65.

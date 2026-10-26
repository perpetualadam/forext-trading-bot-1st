# R.67C Contract clarifications

R.67A and R.67B were not rewritten. The reference model implements the fail-closed reading below. Each item is a proposed correction for a later contract edit.

## C1. Requested-unit fill is not broker-flat

| Field | Value |
| --- | --- |
| Documents | `R67B_CLOSE_LIFECYCLE.md` state table and the transition `CLOSE_SUBMITTING` to `CLOSE_FULLY_CONFIRMED`; `R67A_AUTHORITY_MODEL.md` partial-reduction rule |
| Conflict | `CLOSE_FULLY_CONFIRMED` is defined as the granted units being filled, and also as a later read that shows the side flat. The name reads as if the position itself is flat. |
| Safety consequence | A 5,000 fill against a 10,000 position can be treated as a full flatten, and the remaining 5,000 can be dropped. |
| Proposed correction | Keep the state name. Define it only as "this operation's authorised units were filled." Broker flat stays `FLAT_CONFIRMED` / `BROKER_FLAT_CONFIRMED` on a separate exposure field. |
| Invariant change | No. It states invariant 14, which R.67B already requires when the fill rule is read as granted units. |
| Tests | Scenario 28, `test_requested_5000_of_10000_keeps_remainder` |
| Class | `REQUIRES_CONTRACT_CLARIFICATION` |

## C2. Unlinked flat read does not confirm the bot attempt

| Field | Value |
| --- | --- |
| Documents | `R67B_CLOSE_LIFECYCLE.md` transition `CLOSE_OUTCOME_UNKNOWN` to `CLOSE_FULLY_CONFIRMED` ("read shows each granted trade closed"); `R67A_AUTHORITY_MODEL.md` ambiguous-close section, which allows `OBSERVED_FLAT` without minting a grant |
| Conflict | The B row promotes an ambiguous attempt to fully confirmed when a later read shows flat. R.67A does not require that read to be the bot's fill. A human can close during the ambiguity. |
| Safety consequence | The bot would attribute a human close to itself and could then retire the record and send another close. |
| Proposed correction | Exposure may become `FLAT_CONFIRMED` when the closing-transaction bar is met. The attempt stays `CLOSE_OUTCOME_UNKNOWN` or moves to `CLOSE_MANUAL_REVIEW_REQUIRED` unless the closing transaction id is already stored on that `close_operation_id`. Attribution stays `UNKNOWN`. Retirement stays blocked. |
| Invariant change | Yes, for that one B transition. It keeps R.67A's "resolution does not mint a grant" and strengthens "unresolved close blocks retirement." |
| Tests | Scenarios 49, 50, 56 |
| Class | `REQUIRES_CONTRACT_CLARIFICATION` |

## C3. Single-flight set is narrower in the index than in the prose

| Field | Value |
| --- | --- |
| Documents | `R67B_CONCURRENCY_AND_PERSISTENCE.md` uniqueness paragraph; `R67B_CLOSE_LIFECYCLE.md` conservative retry rule |
| Conflict | The unique-index sentence lists `CLOSE_SUBMITTING`, `CLOSE_OUTCOME_UNKNOWN`, `CLOSE_RECONCILIATION_REQUIRED`, and `CLOSE_MANUAL_REVIEW_REQUIRED`. The prose also blocks a new close while `CLOSE_PARTIALLY_FILLED` or a requested-unit fill has no post-fill snapshot, and two grants must not both become sendable. |
| Safety consequence | A second grant can be authorised against stale units after a partial fill, or two `CLOSE_AUTHORISED` rows can race. |
| Proposed correction | The pre-send commit is the single-flight point. The unique set also holds `CLOSE_AUTHORISED`, unreconciled `CLOSE_PARTIALLY_FILLED`, and unreconciled `CLOSE_FULLY_CONFIRMED`. |
| Invariant change | No change to "a close cannot be submitted twice." It widens the index so the prose and the index match. |
| Tests | Scenarios 35, 36, 29, and the 5,000-of-10,000 case |
| Class | `REQUIRES_CONTRACT_CLARIFICATION` |

## C4. Absent stop field is not confirmed-unprotected

| Field | Value |
| --- | --- |
| Documents | `R67A_PROTECTION_STATUS_CONTRACT.md` entry rule for `UNPROTECTED_CONFIRMED` |
| Conflict | R.67A enters `UNPROTECTED_CONFIRMED` when a trade read succeeds and the stop field is null or absent. The current parser stores price only and can omit an id that was present (`reconciliation.py` 375–388, `R66-05`). |
| Safety consequence | A dropped field would be reported as confirmed missing protection. |
| Proposed correction | `UNPROTECTED_CONFIRMED` requires the read to be marked as containing the complete stop section, and that section to show no stop. An absent or unknown section stays `PROTECTION_UNKNOWN`. |
| Invariant change | No change to "a local price is not a broker stop." It tightens one entry rule. |
| Tests | Scenarios 13 and 14 |
| Class | `REQUIRES_CONTRACT_CLARIFICATION` |

## C5. Reported zero is a predicate, not flat confirmation

| Field | Value |
| --- | --- |
| Documents | `R67B_RECONCILIATION_STATE_MACHINE.md` complete-snapshot and flat-transition rows; `R67A_POSITION_OWNERSHIP_CONTRACT.md` `OBSERVED_FLAT` |
| Conflict | A complete OpenPositions body can show a side at zero, or omit it, without a closing transaction. R.67B already refuses `BROKER_FLAT_CONFIRMED` in that case and keeps prior units. The exposure enum has no separate name for "reported zero." |
| Safety consequence | Calling that snapshot `FLAT_CONFIRMED` retires a live position. |
| Proposed correction | Keep prior authoritative units. Set predicate `exposure_zero_reported`. Enter `FLAT_CONFIRMED` only with a closing transaction id when the previous read had units. |
| Invariant change | No. This is the R.67B rule, named as a predicate. |
| Tests | Scenarios 20, 49, 55 |
| Class | `CONSISTENT_WITH_APPROVED_CONTRACT` |

## C6. Freshness durations are unnamed

| Field | Value |
| --- | --- |
| Documents | `R67A_PROTECTION_STATUS_CONTRACT.md` `PROTECTION_FRESHNESS`; `R67B_RECONCILIATION_STATE_MACHINE.md` `BROKER_SNAPSHOT_FRESHNESS` |
| Conflict | Neither document sets a duration, on purpose, so a trading parameter is not invented. |
| Safety consequence | An implementation that picks a number without review would change a parameter. |
| Proposed correction | Leave both symbols unnamed until a later reviewed stage. The reference model takes an explicit `fresh` flag from the scenario. |
| Invariant change | No. |
| Tests | Scenarios 15, 18, 19, 20, 26 |
| Class | `CONSISTENT_WITH_APPROVED_CONTRACT` |

## C7. Close attribution is its own field

| Field | Value |
| --- | --- |
| Documents | `R67A_POSITION_OWNERSHIP_CONTRACT.md` provenance classes; `R67B_RECONCILIATION_STATE_MACHINE.md` manual-close row |
| Conflict | A and B say the bot must not claim a human close. They do not name `BOT_ATTEMPT_CONFIRMED`, `EXTERNAL_ACTION_CONFIRMED`, and `UNKNOWN`. |
| Safety consequence | A size change can be mistaken for proof of who acted. |
| Proposed correction | Store attribution separately. A snapshot that changes units does not set it. `EXTERNAL_ACTION_CONFIRMED` requires an explicit external actor token on the closing evidence. `BOT_ATTEMPT_CONFIRMED` requires fill evidence stored on that close operation. |
| Invariant change | No. It names a distinction A and B already require. |
| Tests | Scenarios 21, 48, 49, 50 |
| Class | `CONSISTENT_WITH_APPROVED_CONTRACT` |

## What was not found

No pair of R.67A and R.67B rules forced the reference model to send a close, retire a live position, or label a fallback price as broker protection. The model was not blocked. C2 changes one written B transition, so the approved text is not fully validated until that row is corrected.

Final design status for this stage: `R67_DESIGN_PARTIALLY_VALIDATED`.

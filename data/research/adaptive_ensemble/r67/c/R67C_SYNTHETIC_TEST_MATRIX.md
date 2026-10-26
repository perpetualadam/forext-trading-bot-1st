# R.67C Synthetic test matrix

Every scenario below was executed on Windows and WSL2. Expected and actual values matched on both. Result for each row: `PASS`. No scenario was accepted merely because an exception was absent. Each one asserts observation, management, execution, send permission, duplicate-close block, exposure, close state, attribution, protection, flat permission, retirement permission, and manual review.

The synthetic account is `ACC-SYNTHETIC`. Units are decimal strings. A full close of 10,000 requested units does not by itself mark the position flat or retire it.

| # | Scenario | Decisive actual outcome |
| --- | --- | --- |
| 1 | Unknown position discovered | Observation only. Provenance `EXTERNAL_UNKNOWN`. No management, no send. |
| 2 | Manual position discovered | Provenance `MANUAL_ASSERTED`. `execution_kind` close refused. |
| 3 | `log_only` reconciliation | Snapshot refresh. `log_only` close refused. Management false. |
| 4 | Management absent | Management false. Execution false. Send false. |
| 5 | Execution absent | Monitor grant sets management. Send false. |
| 6 | Import attempts close | `reconcile_import` and `execution_kind` refused. |
| 7 | Revoked before submission | Grant dead. Pre-send false. State `CLOSE_NOT_REQUESTED`. |
| 8 | Revoked during in-flight | State `CLOSE_OUTCOME_UNKNOWN`. Send false. Another close blocked. |
| 9 | Snapshot changes after grant | Authorised close cancelled. Pre-send false. |
| 10 | Restart with persisted grant | Execution set empty. Pre-send false. |
| 11 | Broker stop with id and price | `BROKER_PROTECTED`. Confirmed price stored. Local price empty. |
| 12 | Local fallback only | `LOCAL_REFERENCE_ONLY`. Confirmed price empty. |
| 13 | Broker stop disappears | Complete stop section, no stop: `UNPROTECTED_CONFIRMED`. |
| 14 | Incomplete stop payload | `PROTECTION_UNKNOWN`. |
| 15 | Stale protection | `PROTECTION_STALE`. |
| 16 | Restart with local reference only | Stays `LOCAL_REFERENCE_ONLY`. Not `BROKER_PROTECTED`. |
| 17 | Complete snapshot | Exposure `OPEN`. Units unchanged. |
| 18 | Incomplete snapshot | Exposure `STALE`. Flat false. |
| 19 | API timeout | Exposure `STALE`. Flat false. |
| 20 | Stale snapshot reporting zero | Exposure `STALE`. Flat false. |
| 21 | Manual close with closing transaction | Flat confirmed. Attribution `EXTERNAL_ACTION_CONFIRMED`. Retire succeeds. Active observation ends. |
| 22 | Snapshot reduces 10,000 to 6,000 | Exposure `PARTIALLY_OPEN`. Attribution `UNKNOWN`. |
| 23 | Two trades on one side | Two observations. Neither is managed. |
| 24 | Long and short together | Monitor and close refused. |
| 25 | Conflicting reads | Exposure `CONFLICT`. Flat false. |
| 26 | Stale zero then newer 10,000 | Exposure `OPEN`. Flat false. |
| 27 | Epoch 5 then epoch 4 | Units stay 8,000. Older snapshot ignored. |
| 28 | Full fill of 10,000 requested | `CLOSE_FULLY_CONFIRMED`. Attribution bot. Authoritative units still 10,000. Flat false. Retire false. Another close blocked until a later snapshot. |
| 29 | 10,000 requested, 4,000 filled | `CLOSE_PARTIALLY_FILLED`. Units remain 10,000. |
| 30 | Reject | `CLOSE_REJECTED`. Exposure `OPEN`. |
| 31 | Timeout | `CLOSE_OUTCOME_UNKNOWN`. Second grant refused. Second send refused. |
| 32 | Acknowledgement lost | `CLOSE_OUTCOME_UNKNOWN`. Attribution `UNKNOWN`. |
| 33 | Unknown, then a read still showing 10,000 | Pending id kept. State stays unknown. Not rejected. |
| 34 | Repeat while unresolved | Second grant and second pre-send refused. |
| 35 | Two grants | Second grant is none. First remains `CLOSE_AUTHORISED`. Send false until pre-send. |
| 36 | Two submitters | One pre-send. One send. Second send false. |
| 37 | Commit failure before pre-send | No close row. No send. |
| 38 | Commit failure after pre-send | State stays `CLOSE_SUBMITTING`. Fill not stored. Units unchanged. |
| 39 | Restart during submitting | State `CLOSE_OUTCOME_UNKNOWN`. Send false. Execution empty. |
| 40 | Restart during unknown | State stays unknown. New grant refused. |
| 41 | HTTP body with price and P&L only | `CLOSE_RECONCILIATION_REQUIRED`. |
| 42 | Duplicate full-fill response | Confirmed units stay 10,000. |
| 43 | Fill epoch older than a newer open snapshot | `CLOSE_MANUAL_REVIEW_REQUIRED`. Exposure `CONFLICT`. Units stay 10,000. |
| 44 | Fill and cancel in one body | Fill wins. `CLOSE_FULLY_CONFIRMED`. |
| 45 | Fill units disagree with `tradesClosed` | `CLOSE_RECONCILIATION_REQUIRED`. Confirmed units 0. |
| 46 | Unknown trade id in `tradesClosed` | `CLOSE_RECONCILIATION_REQUIRED`. Attribution `UNKNOWN`. |
| 47 | Same fill transaction id twice | Confirmed units stay 4,000. |
| 48 | Fewer units, no actor | `PARTIALLY_OPEN`. Attribution `UNKNOWN`. |
| 49 | Snapshot says zero, no closing transaction | `exposure_zero_reported` true. Authoritative units stay 10,000. Flat false. |
| 50 | Human close during unknown bot close | Exposure flat. Close `CLOSE_MANUAL_REVIEW_REQUIRED`. Attribution `UNKNOWN`. Retire false. |
| 51 | Two contradictory trade reads | Exposure `CONFLICT`. |
| 52 | Full-fill claim, then newer exposure, then conflict | Manual review. Flat false. Retire false. |
| 53 | Drop local row while units remain | Drop refused. Retire refused. Observation remains. |
| 54 | Flat with closing transaction | Retire returns true. Row `retired` and `flat_confirmed`. |
| 55 | Closure call without a transaction id | Flat false. Retire false. |
| 56 | Flat evidence while close unresolved | Flat true. Manual review. Retire false. |
| 57 | Partial response commit fails | State stays `CLOSE_SUBMITTING`. Confirmed units 0. Broker units 10,000. |
| 58 | Reconcile during `CLOSE_SUBMITTING` | Pending id kept. One send still allowed. Second grant refused. |
| 59 | Stale observation version | Compare-and-swap loses. Loser records `reread_no_send`. Units not forced to zero. |
| 60 | Recovery commit fails | `recovery_blocked`. Send false. New grant refused. Durable state stays `CLOSE_SUBMITTING`. |

## Additional cases outside the numbered 60

| Case | Actual outcome | Result |
| --- | --- | --- |
| Authorise 5,000 of 10,000 and fill 5,000 | Close `CLOSE_FULLY_CONFIRMED`. Exposure stays `OPEN` at 10,000. Retire false. New grant refused until a snapshot shows 5,000. After that snapshot, exposure `PARTIALLY_OPEN` and a new grant is a new id. | PASS |
| 7,000 fill across T1 and T2 | `CLOSE_PARTIALLY_FILLED`. Neither trade's authoritative units move. Neither retires. | PASS |
| Fill with `tradesClosed` null | `CLOSE_RECONCILIATION_REQUIRED`. | PASS |
| Partial fill, snapshot of the remainder, then external close | Bot attribution stays on the operation. Exposure attribution becomes external. | PASS |
| Partial fill then stale zero snapshot | Exposure `STALE`. Units stay 10,000. Flat false. | PASS |
| Partial fill then restart | State stays `CLOSE_PARTIALLY_FILLED`. Execution empty. New grant refused. | PASS |
| Send before pre-send | False. | PASS |
| Commit during broker wait | `LockAcrossIO`. | PASS |
| Expire grant while unknown | Unknown operation remains. New grant refused. | PASS |
| 200 sequences, 12 steps, seed 67 | Invariants held after every step. | PASS |

## Coverage gaps

- Live OpenPositions, TradeDetails, and PositionClose bodies were not fetched.
- PostgreSQL isolation and locking were not tested.
- No duration was assigned to `PROTECTION_FRESHNESS` or `BROKER_SNAPSHOT_FRESHNESS`.
- `TradeClose` is not a modelled sender.
- Client-extension echo and host acceptance of decimal units were not tested.
- Account hedging permission was not tested. The model refuses management while both sides have units.
- Hypothesis was not used. Generation is `random.Random(67)`.
- The same stage wrote the model and the expected literals. Negative refusals and the invariant sweep reduce self-confirmation. They do not remove it.
- The operational bot was not executed, so these passes are not bot passes.

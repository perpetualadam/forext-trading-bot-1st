# R.86 Snapshot Provenance Contract

Evidence: the implemented shape in `forex_bot/exposure_report.py`, executed by the R.86 tests. This is a read-only contract. It is not wired into startup recovery.

An observation carries:

| Field | Rule |
| --- | --- |
| Observation identifier | Derived from endpoint, account, epoch, timestamp, completeness, and trade count |
| Source operation | `OpenPositions` for this adapter |
| Origin | `synthetic` in tests. An operational call would be labelled separately. No operational call was made |
| Expected account | Caller-supplied |
| Observed account | `accountID` when the body has it |
| Monotonic start and completion | Caller-supplied integers. Wall time is not the order key |
| UTC timestamp | Caller-supplied. Missing means freshness is not established |
| Process id | Optional |
| Recovery epoch | The epoch observed at classification, not a grant of authority |
| Validation | `parsed_single_response`, `malformed`, `account_mismatch`, `stale`, or a failure reason |
| Completeness | `UNKNOWN_COMPLETENESS`, `INCOMPLETE`, `FAILED`, or `STALE` |
| Pagination | `NOT_REPRESENTED` for the adapter |
| Pages observed | 1 for a single body, 0 when the body is missing |
| Trade count | Count of parsed nonzero sides with trade ids |
| Transaction watermark | Always null from this adapter |
| Reporting suitability | True only for a parsed single response that is not stale |
| Recovery suitability | Always false |

`COMPLETE_VERIFIED` is defined so callers can name it, and the report downgrades that label to `UNKNOWN_COMPLETENESS`. A fixture that says `COMPLETE` is not accepted as proof. A timestamp is not proof that every broker transaction is inside the body.

`assess_supplied_pages` evaluates records a caller already has. It exists so missing, repeated, and conflicting pages have a deterministic result. It is not an OpenPositions pagination client, and it never returns `COMPLETE_VERIFIED`.

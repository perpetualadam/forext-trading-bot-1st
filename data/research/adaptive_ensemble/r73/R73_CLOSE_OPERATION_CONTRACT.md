# R.73 Close Operation Contract

Implemented in `forex_bot/broker_close_evidence.py`. `CloseOperation` starts at line 60. `run_guarded_live_close` starts at line 494.

## States

`CLOSE_NOT_REQUESTED`, `CLOSE_PREPARED`, `CLOSE_SUBMITTING`, `CLOSE_SUBMITTED` (recorded as submission state `SENT` plus a confirmation state), `CLOSE_RESPONSE_RECEIVED`, `CLOSE_CONFIRMATION_PENDING`, `CLOSE_PARTIALLY_CONFIRMED`, `CLOSE_FULLY_CONFIRMED`, `CLOSE_REJECTED_CONFIRMED`, `CLOSE_OUTCOME_AMBIGUOUS`, `CLOSE_RECONCILIATION_REQUIRED`.

Submission state is separate: `NOT_SENT`, `SENDING`, `SENT`.

## Recorded fields

Operation id, account scope (`scoped`, `matched`, `missing`), instrument, direction, trade ids, local identity string, original units, requested units, confirmed units, remaining units, broker request identity (empty, because the close body has no client idempotency key), transaction ids, both states, error classification, attempt count, timestamps, evidence source, and submission count.

Units are `Decimal`. A missing or non-finite quantity stays `None`. It is not stored as zero. A confirmed rejection or an explicit closed-unit value of zero may store `Decimal("0")` because the body stated that quantity.

## What blocks another submission

Prepared, submitting, sent, response received, confirmation pending, partially confirmed, ambiguous, reconciliation required, and fully confirmed.

A confirmed broker rejection removes the in-process blocker. The row stays. A later cycle may reserve a new operation. An ambiguous result keeps the same operation id.

`R73_CLOSE_OPERATION_MODEL_IMPLEMENTED`

`R73_AMBIGUOUS_CLOSE_BLOCKS_RESUBMISSION`

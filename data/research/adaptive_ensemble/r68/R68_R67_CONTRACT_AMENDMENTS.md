# R.68 amendments to the R.67 contracts

These are accepted design corrections. They do not rewrite `data/research/adaptive_ensemble/r67/a/` or `data/research/adaptive_ensemble/r67/b/`. R.68 operational code does not implement the close state machine, the unique index, or a new stop parser.

Source of the conflict record: `data/research/adaptive_ensemble/r67/c/R67C_CONTRACT_CLARIFICATIONS.md`.

## C2 — Ambiguous close attribution

### Original rule

`R67B_CLOSE_LIFECYCLE.md` state table:

> `CLOSE_FULLY_CONFIRMED` — Fill evidence covers the granted units, or a later read shows the side flat with closing transactions covering those units.

Same document, transition diagram:

> `CLOSE_OUTCOME_UNKNOWN --> CLOSE_FULLY_CONFIRMED: read shows flat`

R.67C C2 names the same edge as "read shows each granted trade closed" and notes that `R67A_AUTHORITY_MODEL.md` allows `OBSERVED_FLAT` without minting a grant.

### Replacement wording

A broker-flat observation does not confirm that the bot's ambiguous close succeeded.

`CLOSE_OUTCOME_UNKNOWN` stays `CLOSE_OUTCOME_UNKNOWN`, or moves to `CLOSE_MANUAL_REVIEW_REQUIRED`, unless the closing transaction id is already stored on that `close_operation_id`. An unlinked closing transaction cannot promote the attempt to `CLOSE_FULLY_CONFIRMED`.

Close attribution stays `UNKNOWN` until evidence is linked to that close operation. An unresolved close stays blocked from another close, or enters manual review. Local retirement stays blocked while the close attempt is unresolved.

Exposure may become `FLAT_CONFIRMED` only when the closing-transaction bar for the exposure record is met. That exposure update does not classify the ambiguous attempt.

### Justification

R.67C C2. A later flat read can be a human close. Promoting the bot attempt would attribute that close to the bot and could retire the local record.

### Operational status

Design correction only. R.68 does not add `close_operation_id`, attribution, or retirement rules to the bot.

## C3 — Single-flight coverage

### Original rule

`R67B_CONCURRENCY_AND_PERSISTENCE.md`:

> Single-flight is a uniqueness rule: at most one close operation for a given account, instrument, and book side may be in `CLOSE_SUBMITTING`, `CLOSE_OUTCOME_UNKNOWN`, `CLOSE_RECONCILIATION_REQUIRED`, or `CLOSE_MANUAL_REVIEW_REQUIRED`. A second insert fails and must not call the network.

`R67B_CLOSE_LIFECYCLE.md` also blocks a new close while `CLOSE_PARTIALLY_FILLED` or a requested-unit completion has no later snapshot, and it forbids two grants both becoming sendable.

### Replacement wording

The blocking set is:

- `CLOSE_AUTHORISED`
- `CLOSE_SUBMITTING`
- `CLOSE_OUTCOME_UNKNOWN`
- `CLOSE_RECONCILIATION_REQUIRED`
- `CLOSE_MANUAL_REVIEW_REQUIRED`
- Unreconciled `CLOSE_PARTIALLY_FILLED`
- Unreconciled requested-unit completion (`CLOSE_FULLY_CONFIRMED` for the requested units while the remainder has not been read)

A second insert in that set fails and must not call the network. The pre-send commit remains the single-flight point.

### Justification

R.67C C3. The index sentence was narrower than the prose, so a second `CLOSE_AUTHORISED` row or a grant after an unreconciled partial could race.

### Operational status

Design correction only. R.68 does not create the unique index and does not add a close-operation table.

## C4 — Protection completeness

### Original rule

`R67A_PROTECTION_STATUS_CONTRACT.md`:

> `UNPROTECTED_CONFIRMED` — A fresh `TradeDetails` read for that trade id succeeded, and the stop order field is null or absent. The read is inside `PROTECTION_FRESHNESS`.

> `LOCAL_REFERENCE_ONLY` — A local or copied price exists, and the broker stop id is absent. This includes the 20-pip fallback from `sl_tp_distance_for_entry`.

> `PROTECTION_UNKNOWN` — No successful trade read, the read errored, the trade id list is empty, both sides have units, or the account id is missing.

### Replacement wording

`UNPROTECTED_CONFIRMED` requires a read marked as containing the complete broker stop section, and that section showing no protective stop.

An absent, truncated, or unknown stop section remains `PROTECTION_UNKNOWN`.

A local fallback price remains `LOCAL_REFERENCE_ONLY`. It is not `BROKER_PROTECTED` and it is not `UNPROTECTED_CONFIRMED`.

### Justification

R.67C C4. The current parser stores a stop price and can drop an id that was present (`reconciliation.py` stop-field handling, R66-05). A missing field in that parser is not proof that the broker has no stop.

### Operational status

Design correction only. R.68 does not change stop parsing, `broker_sl_tp_hit`, or profit-protection formulas.
